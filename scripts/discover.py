#!/usr/bin/env python3
"""Discovery of new work: a candidate queue, not registry records.

A work that has been found is not a technology but a supposition about one. The
decision that this is a new architecture rather than an application of an
existing one belongs to a person: a rule errs here, and the price of the error
is a registry record about something that does not exist. Discovery therefore
**creates no records** and appends lines to `data/candidates.jsonl`.

The journal is append-only, like the evidence. A verdict is entered separately
and states a decision: `accepted` means a registry record now exists, `rejected`
means the reason is written down and the candidate will not surface again.

Filtering before review is done mechanically and without a language model: what
is already in the registry by preprint number or by name is dropped, and so is
what already carries a verdict. Filtering on the substance, deciding that this
is an application rather than an architecture, is not delegated to a machine.

Usage::

    python3 scripts/discover.py                 # the past week
    python3 scripts/discover.py --since 30      # the past thirty days
    python3 scripts/discover.py --dry-run       # show without writing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.candidate_fit import assess  # noqa: E402
from services.collectors.curated import CURATED_LISTS, discover_from_lists  # noqa: E402
from services.collectors.paperswithcode import RAG_METHOD, Paper, discover  # noqa: E402
from services.registry import store  # noqa: E402

CANDIDATES = store.DATA_DIR / "candidates.jsonl"
REJECTED = store.DATA_DIR / "rejected.jsonl"

#: How far back to ask for work by default. It matches the schedule: a day of
#: overlap is cheaper than a gap, and a repeat is filtered out by its number.
DEFAULT_WINDOW_DAYS = 8

#: The window for curated lists: two years rather than a week.
#:
#: A list grows not on a schedule but when whoever keeps it gets round to it, and
#: a work may enter it half a year after it appeared. A week-long window, right
#: for the catalogue, would cut off exactly what the list is asked for. What is
#: already known is filtered out before the archive is asked, so the wide window
#: costs one parse of the markup rather than a hundred requests.
CURATED_WINDOW_DAYS = 730

_ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})")


@dataclass
class DiscoverySummary:
    """What discovery came to: what was found, what was filtered, and why."""

    found: int = 0
    added: int = 0
    known: int = 0
    decided: int = 0
    rescored: int = 0
    problems: list[str] = field(default_factory=list)


def load_candidates() -> list[dict]:
    if not CANDIDATES.exists():
        return []
    return [
        json.loads(line)
        for line in CANDIDATES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _registry_arxiv_ids() -> set[str]:
    """The preprint numbers the registry already points at."""
    found: set[str] = set()
    for tech in store.load_technologies():
        for link in tech.links:
            match = _ARXIV_ID.search(link.url)
            if match:
                found.add(match.group(1))
    return found


def _registry_names() -> set[str]:
    names: set[str] = set()
    for tech in store.load_technologies():
        names.add(tech.name.strip().lower())
        names |= {alias.strip().lower() for alias in tech.aliases}
    return names


def _rejected_names() -> set[str]:
    if not REJECTED.exists():
        return set()
    out: set[str] = set()
    for line in REJECTED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        name = row.get("name")
        if name:
            out.add(name.strip().lower())
    return out


def is_known(paper: Paper, *, arxiv_ids: set[str], names: set[str]) -> bool:
    """The work is already in the registry or was refused before.

    The comparison goes by preprint number and by name. The name is compared in
    full: the title of a work is usually longer than the name of a technology,
    so substring matching would produce false positives on common words.
    """
    if paper.arxiv_id in arxiv_ids:
        return True
    title = paper.title.strip().lower()
    if title in names:
        return True
    # A title of the form "HippoRAG: Neurobiologically Inspired...": the name
    # stands before the colon, and a registry record is recognised by it.
    head = title.split(":", 1)[0].strip()
    return bool(head) and head in names


def run(
    *,
    since_days: int = DEFAULT_WINDOW_DAYS,
    today: date | None = None,
    http=None,
    dry_run: bool = False,
) -> DiscoverySummary:
    today = today or date.today()
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport()

    summary = DiscoverySummary()
    papers, problems = discover(
        http=http, published_after=today - timedelta(days=since_days),
        method=RAG_METHOD,
    )
    summary.problems.extend(problems)

    arxiv_ids = _registry_arxiv_ids()
    names = _registry_names() | _rejected_names()
    seen = {row.get("arxiv_id") for row in load_candidates()}
    decided = {
        row.get("arxiv_id") for row in load_candidates() if row.get("verdict")
    }

    # The second route of discovery: curated topic lists.
    #
    # The catalogue finds a work by a tag applied by whoever uploaded it. A list
    # finds a work by the decision of a person who works in the subject. The two
    # routes complement each other, and a work found by both is not a duplicate
    # but the agreement of two independent selections.
    #
    # What is known is filtered out before the archive is asked: a list holds a
    # hundred-odd works of which a handful are new, and asking for every abstract
    # would hammer somebody else's service to no purpose.
    listed, listed_problems = discover_from_lists(
        http=http,
        published_after=today - timedelta(days=CURATED_WINDOW_DAYS),
        known=arxiv_ids | seen | decided,
    )
    summary.problems.extend(listed_problems)
    curated_source = {paper.arxiv_id for paper in listed}
    papers = papers + listed
    summary.found = len(papers)

    fresh: list[dict] = []
    for paper in papers:
        if is_known(paper, arxiv_ids=arxiv_ids, names=names):
            summary.known += 1
            continue
        if paper.arxiv_id in decided:
            summary.decided += 1
            continue
        if paper.arxiv_id in seen:
            continue  # already in the queue, awaiting a verdict
        curated = sorted(
            source.name for source in CURATED_LISTS
            if paper.arxiv_id in curated_source
        )
        fit = assess(title=paper.title, abstract=paper.abstract,
                     tasks=[{"slug": slug} for slug in paper.tasks],
                     curated_by=curated)
        fresh.append({
            "found_at": today.isoformat(),
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "tasks": paper.tasks,
            "fit": fit.as_dict(),
            "published": paper.published.isoformat() if paper.published else None,
            "source": paper.url,
            "citations": paper.citations,
            "repositories": paper.repositories,
            # Where the work came from. It matters when the queue is worked
            # through: a find from a list and a find from the catalogue are
            # corroborated by different things, and knowing which is more use to
            # a person than a single fitness number.
            "curated_by": curated,
            "verdict": None,
        })

    summary.added = len(fresh)
    if fresh and not dry_run:
        CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
        with CANDIDATES.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    summary.rescored = rescore(dry_run=dry_run)
    return summary


def rescore(*, dry_run: bool = False) -> int:
    """Recompute the fitness of the candidates awaiting a verdict.

    The scoring rule changes more often than the queue does: the list of tags is
    refined as it becomes clear what the catalogue actually applies. A candidate
    in its third week in the queue should be judged by the current rule and not
    by the one in force on the day it was found, or the order of review lies.

    It needs no network: the task tags, the abstract and the provenance of the
    find are stored with the candidate. The provenance has to be handed back to
    the scoring explicitly: the recomputation works from the queue line, and a
    signal derived at discovery but not stored would be lost on recomputation.
    That is exactly what happened once — the scores of works found through lists
    were zeroed by the first recomputation.
    """
    rows = load_candidates()
    if not rows:
        return 0
    changed = 0
    for row in rows:
        if row.get("verdict"):
            continue
        fit = assess(
            title=row.get("title", ""),
            abstract=row.get("abstract", ""),
            tasks=[{"slug": slug} for slug in row.get("tasks", [])],
            curated_by=row.get("curated_by") or None,
        ).as_dict()
        if row.get("fit") != fit:
            row["fit"] = fit
            changed += 1
    if changed and not dry_run:
        CANDIDATES.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
            + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=int, default=DEFAULT_WINDOW_DAYS,
                        help="how many days back to ask for work")
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    args = parser.parse_args()

    summary = run(since_days=args.since, dry_run=args.dry_run)
    print(
        f"discovery: found {summary.found}, added to the queue "
        f"{summary.added}, already in the registry {summary.known}, decided "
        f"before {summary.decided}, rescored {summary.rescored}"
    )
    for problem in summary.problems[:10]:
        print(f"  {problem[:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
