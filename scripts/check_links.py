#!/usr/bin/env python3
"""Check that the registry's links resolve.

A link is the only thing separating a record from a mention: without a
resolvable source, the name of a technology confirms nothing. The check runs in
the weekly pass because links rot in silence — a venue moves, a preprint is
withdrawn, a repository is renamed, and the record goes on looking grounded.

Three outcomes are distinguished, and the distinction matters:

* **it resolves** — the mark becomes `verified` with a date, so a reader sees
  that the link was opened rather than merely written down;
* **it does not exist** — a 404 or a 410 gives the mark `unresolved`: the
  address points into nothing, and that has to be repaired by hand;
* **it is unclear** — a refusal on rights, a rate limit, a network error, a
  server failure. The mark does not change at all.

The last rule is the important one. A temporary refusal must not turn a verified
link into a non-existent one: publishers refuse robots and networks break, and
the record would then look damaged while nothing is wrong with it.

The allowlist of hosts is deliberately lifted here. It guards evidence
collection from wandering to addresses met in the content of sources, whereas
the registry's links were written by us and many of them lead to venues the list
does not contain.

Usage::

    python3 scripts/check_links.py              # check and set the marks
    python3 scripts/check_links.py --dry-run    # show what would change
    python3 scripts/check_links.py --stale 30   # only those unchecked for 30 days
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: Codes meaning the address does not exist. Everything else is not a verdict.
GONE = (404, 410)

#: Codes meaning "it is there and it will not show": rights, payment, bot walls.
GUARDED = (401, 402, 403, 429)


@dataclass
class LinkSummary:
    """What a pass over the links came to."""

    checked: int = 0
    verified: int = 0
    gone: int = 0
    guarded: int = 0
    errored: int = 0
    changed: int = 0
    problems: list[str] = field(default_factory=list)


def _outcome(status: int) -> str:
    if 200 <= status < 400:
        return "verified"
    if status in GONE:
        return "unresolved"
    if status in GUARDED:
        return "guarded"
    return "unknown"


def run(
    *,
    http=None,
    today: date | None = None,
    dry_run: bool = False,
    stale_after: int = 0,
) -> LinkSummary:
    """Walk the registry's links and update their marks.

    `stale_after`, in days, spares the recently confirmed links a second check:
    an address that opened yesterday rarely vanishes within a week, and a
    superfluous request spends somebody else's resources and your own time.
    """
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport(allow_any_host=True)
    today = today or date.today()
    summary = LinkSummary()

    # An address is checked once even when several records carry it: the
    # outcome does not depend on the record.
    outcomes: dict[str, tuple[str, int]] = {}

    for tech in store.load_technologies():
        touched = False
        for link in tech.links:
            if not link.url.strip():
                continue
            # Recently inspected addresses are skipped, and so are those closed
            # by rights: a venue that refused a robot yesterday will refuse it
            # today, and the request would spend somebody else's resources for
            # an answer already known.
            if (
                stale_after
                and link.status in ("verified", "guarded")
                and link.verified_at is not None
                and today - link.verified_at < timedelta(days=stale_after)
            ):
                continue

            if link.url not in outcomes:
                summary.checked += 1
                try:
                    status, _ = http.get(link.url, timeout=20)
                except Exception as exc:  # a broken network is no verdict on a link
                    outcomes[link.url] = ("unknown", 0)
                    summary.problems.append(f"{tech.id}: {link.url} — {exc}"[:160])
                else:
                    outcomes[link.url] = (_outcome(status), status)

            verdict, status = outcomes[link.url]
            if verdict == "verified":
                summary.verified += 1
                if link.status != "verified" or link.verified_at != today:
                    link.status = "verified"
                    link.verified_at = today
                    touched = True
            elif verdict == "unresolved":
                summary.gone += 1
                summary.problems.append(
                    f"{tech.id}: {link.url} answers with {status}"
                )
                if link.status != "unresolved":
                    link.status = "unresolved"
                    link.verified_at = None
                    touched = True
            elif verdict == "guarded":
                # A refusal on rights does not demote a confirmed link:
                # publishers answer robots that way, and taking it for the death
                # of an address would spoil the registry faster than time spoils
                # addresses.
                #
                # But leaving an unchecked link in its former state is no better.
                # It stuck in "nobody looked" for ever although it was looked at
                # every week, and telling it from one truly never checked was
                # impossible. The mark `guarded` asserts exactly what was
                # observed: the request was made, the address answered, and it
                # declined to show itself to a robot. Only a person can confirm
                # it.
                summary.guarded += 1
                if link.status == "verified":
                    summary.problems.append(
                        f"{tech.id}: {link.url} answers with {status} "
                        "(the check mark is kept)"
                    )
                elif link.status != "guarded" or link.verified_at != today:
                    link.status = "guarded"
                    link.verified_at = today
                    touched = True
                    summary.problems.append(
                        f"{tech.id}: {link.url} answers with {status}, "
                        "only a person can confirm it"
                    )
            else:
                # A broken connection, a timeout, an unknown code: the mark is
                # left alone, because none of it says anything about the address.
                summary.errored += 1
                if status:
                    summary.problems.append(
                        f"{tech.id}: {link.url} answers with {status} "
                        "(the mark is unchanged)"
                    )

        if touched and not dry_run:
            store.save_technology(tech)
            summary.changed += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument(
        "--stale", type=int, default=0,
        help="skip links confirmed within the last N days",
    )
    args = parser.parse_args()

    summary = run(dry_run=args.dry_run, stale_after=args.stale)
    print(
        f"addresses checked {summary.checked}: "
        f"resolving {summary.verified}, gone {summary.gone}, "
        f"closed by rights {summary.guarded}, request errors {summary.errored}"
    )
    print(f"records changed: {summary.changed}")
    for problem in summary.problems:
        print(f"  {problem}")
    return 1 if summary.gone else 0


if __name__ == "__main__":
    raise SystemExit(main())
