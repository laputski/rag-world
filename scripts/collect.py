#!/usr/bin/env python3
"""Collect evidence from open sources.

The first step of the update chain. It walks the sources of every record, asks
the preprint archive, the open index, the code host and the works-and-code
catalogue, runs the deterministic checks and appends what passes to the evidence
journal. No language model takes part.

The checks are deterministic on principle: an identifier resolves, a title
matches, a value falls in range. Two language models agreeing is not accepted as
confirmation, because they are trained on overlapping data and err in the same
direction.

Evidence entered by a person is loaded separately, from
`data/manual_evidence.jsonl`. It is needed where no machine-readable source
exists: industrial use, independent reproduction, publication at a venue the
open indexes do not know. Every such entry must carry a link and is marked as
entered by a person.

Usage::

    python3 scripts/collect.py                 # every record
    python3 scripts/collect.py --limit 5       # the first five, as a trial
    python3 scripts/collect.py --only pathrag  # one record
    python3 scripts/collect.py --dry-run       # write nothing
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.collectors.base import RawEvidence  # noqa: E402
from services.collectors.s5 import check_many  # noqa: E402
from services.registry import store  # noqa: E402

MANUAL_FILE = store.DATA_DIR / "manual_evidence.jsonl"

_VELOCITY_RE = re.compile(r"citation_velocity=([0-9.]+)")
_ARXIV_HOST = "arxiv.org"


def _collectors_for(url: str) -> list[str]:
    """Which collectors apply to a source.

    A preprint address is asked twice over: the archive itself gives the fact of
    the preprint, and the open index gives the publication venue and the
    citations. Without the second request a work would stay a preprint for ever,
    even after it appeared at a conference.
    """
    if _ARXIV_HOST in url:
        # The works-and-code catalogue is asked by the same preprint number. It
        # gives the publication venue from a second source: while the venue came
        # from the open index alone, an error there was covered by nothing.
        return ["arxiv", "openalex", "paperswithcode"]
    if "github.com" in url:
        return ["github"]
    if "openalex.org" in url:
        return ["openalex"]
    # The open index also resolves a work by its digital identifier, and always
    # could — only the route here was missing. Because of that, a record whose
    # only source was published other than as a preprint received no publication
    # evidence at all: Standard HybridRAG had no level computed, although the
    # technique underlies hybrid search and is described by a work with six
    # hundred citations. The link itself stays closed to a robot, the publisher
    # answering with a refusal on rights, so it is the index that gets asked.
    if "doi.org" in url:
        return ["openalex"]
    return []


def _collect_one(
    tech: store.Technology, *, http, github_token: str | None, today: date
) -> tuple[list[RawEvidence], list[str]]:
    from services.collectors.arxiv import _extract_arxiv_id, collect_arxiv
    from services.collectors.github import collect_github
    from services.collectors.openalex import collect_openalex
    from services.collectors.paperswithcode import collect_venue

    raw: list[RawEvidence] = []
    errors: list[str] = []
    for link in tech.links:
        for kind in _collectors_for(link.url):
            if kind == "arxiv":
                # The label of a link is not the title of a work: it holds notes
                # like "CausalRAG (arXiv:2503.19878, ACL 2025)" and "corrected:
                # was 2406.18542". Comparing those with a real title rejected
                # thirteen legitimate publications on every pass.
                #
                # There is nothing to check here in substance either: the link
                # carries an archive number, and a request by number returns
                # exactly that work. Comparing titles is needed where a work is
                # found by search, that is, in the open index, and there it is.
                result = collect_arxiv(
                    tech.id, link.url, http=http, today=today,
                )
            elif kind == "github":
                result = collect_github(
                    tech.id, link.url, http=http, token=github_token, today=today,
                )
            elif kind == "paperswithcode":
                # The catalogue is asked by preprint number rather than by
                # address: it answers anything it did not understand with a feed
                # of the newest work, and such an answer looks meaningful.
                number = _extract_arxiv_id(link.url)
                if not number:
                    continue
                result = collect_venue(tech.id, number, http=http, today=today)
            else:
                result = collect_openalex(
                    tech.id, link.url, http=http,
                    expected_title=tech.name, today=today,
                )
            raw.extend(result.evidence)
            errors.extend(f"{tech.id}: {e}" for e in result.errors)
    return raw, errors


def _metrics_from(evidence: list[store.Evidence]) -> list[store.MetricPoint]:
    """The attention series, taken from the values of collected evidence.

    The absolute citation count is not kept as a measurement: it is not
    comparable across fields and is out of date at once. What is kept is the
    citation velocity.
    """
    points: list[store.MetricPoint] = []
    for item in evidence:
        match = _VELOCITY_RE.search(item.value or "")
        if match:
            points.append(store.MetricPoint(
                technology_id=item.technology_id,
                metric="citation_velocity",
                value=float(match.group(1)),
                measured_at=item.fetched_at,
                source=item.source,
            ))
    return points


def load_manual_evidence() -> list[store.Evidence]:
    """Evidence entered by a person; every item must carry a link."""
    if not MANUAL_FILE.exists():
        return []
    import json

    out: list[store.Evidence] = []
    for line in MANUAL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        row.setdefault("obtained_by", "manual")
        row.setdefault("verified", True)
        out.append(store.Evidence.model_validate(row))
    return out


@dataclass
class CollectSummary:
    """What the collection came to: what was added and what did not work.

    It is returned to the caller rather than printed: the run log records these
    numbers, and the same ones reach the summary of the pass.
    """

    sources: list[str] = field(default_factory=list)
    evidence_added: int = 0
    metrics_added: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


def gather(
    *,
    limit: int = 0,
    only: str | None = None,
    dry_run: bool = False,
    http=None,
    today: date | None = None,
) -> CollectSummary:
    """Ask the sources and append the evidence that passes the checks.

    `http` and `today` are injected: without that the pass could not be tested
    without a network, and an untested unattended pass is more dangerous than a
    run started by hand.
    """
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport()
    today = today or date.today()
    github_token = os.environ.get("GITHUB_TOKEN") or None

    technologies = store.load_technologies()
    if only:
        technologies = [t for t in technologies if t.id == only]
        if not technologies:
            raise SystemExit(f"no technology {only!r} exists in the registry")
    if limit:
        technologies = technologies[:limit]

    summary = CollectSummary(sources=["arxiv", "openalex", "github", "paperswithcode"])
    accepted: list[store.Evidence] = []
    raw_all: list[RawEvidence] = []

    for tech in technologies:
        raw, tech_errors = _collect_one(
            tech, http=http, github_token=github_token, today=today
        )
        summary.errors.extend(tech_errors)
        raw_all.extend(raw)

    # Framework presence is asked once for the whole registry: what is read is
    # the directory listings, not one record after another.
    from services.collectors.frameworks import collect_frameworks

    framework_evidence, framework_errors = collect_frameworks(
        technologies, http=http, token=github_token, today=today
    )
    raw_all.extend(framework_evidence)
    summary.errors.extend(framework_errors)
    if framework_evidence or not framework_errors:
        summary.sources.append("frameworks")

    # Package downloads only where a person wrote the package name down.
    from services.collectors.pypi import collect_pypi

    polled_pypi = False
    for tech in technologies:
        if not tech.package:
            continue
        polled_pypi = True
        result = collect_pypi(tech.id, tech.package, http=http, today=today)
        raw_all.extend(result.evidence)
        summary.errors.extend(result.errors)
    if polled_pypi:
        summary.sources.append("pypi")

    for item, check in check_many(raw_all):
        if not check.passed:
            summary.rejected += 1
            continue
        accepted.append(store.Evidence(
            technology_id=item.technology_id,
            type=item.type,  # type: ignore[arg-type]
            value=item.value,
            source=item.source,
            fetched_at=item.fetched_at,
            obtained_by="auto",
            verified=True,
        ))

    manual = load_manual_evidence()
    if manual:
        summary.sources.append("manual")
    points = _metrics_from(accepted)

    if dry_run:
        summary.evidence_added = len(accepted) + len(manual)
        summary.metrics_added = len(points)
    else:
        summary.evidence_added = store.append_evidence(accepted + manual)
        summary.metrics_added = store.append_metrics(points)
    return summary


def run(*, limit: int = 0, only: str | None = None, dry_run: bool = False) -> int:
    """Collection on its own; the whole pass lives in scripts/update.py."""
    summary = gather(limit=limit, only=only, dry_run=dry_run)
    prefix = "would add" if dry_run else "added"
    print(
        f"{prefix}: evidence {summary.evidence_added}, "
        f"series points {summary.metrics_added}; "
        f"rejected by the checks {summary.rejected}"
    )
    if summary.errors:
        print(f"sources that yielded nothing: {len(summary.errors)}")
        for message in summary.errors[:10]:
            print(f"  {message[:130]}")
        if len(summary.errors) > 10:
            print(f"  and {len(summary.errors) - 10} more")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="cap the number of records")
    parser.add_argument("--only", help="process one named record")
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    args = parser.parse_args()
    return run(limit=args.limit, only=args.only, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
