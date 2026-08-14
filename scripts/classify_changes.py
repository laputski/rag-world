#!/usr/bin/env python3
"""Classify a registry change: apply it, or show it to a person.

This reasoning used to live inside the workflow, written into YAML. Logic in a
job description is covered by no tests and cannot be run locally, so it moved
here and the workflow stayed a wrapper.

The rule follows from a principle the project rests on: a registry change is
always explicable, and the changes that are hard to undo or easy to miss go
through a person. Three cases are shown:

* **a demotion** — it means either that the previous claim was wrong or that the
  technology has degraded, and both deserve a look;
* **crossing the boundary of confirmed evidence**, that is, entering L4 or
  above — beyond it begin claims about independent reproduction and industrial
  use, where an error costs more;
* **evidence entered by a person** — if it appeared during an automatic pass,
  somebody edited the manual evidence file, and that is worth seeing.

Everything else applies by itself. Sending every change through review is not an
option: the queue would overflow and the review would decay into a formality.

Usage::

    python3 scripts/classify_changes.py            # classify the changes in git
    python3 scripts/classify_changes.py --github   # output for the workflow
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

#: The boundary of confirmed evidence: from this level upwards begin claims of
#: independent reproduction, where an error costs more.
REVIEW_THRESHOLD = "L4"

#: The path of the level journal relative to the root of the repository. It is
#: taken from the store rather than written out: were the journal to move, the
#: parsing would look into nothing and the gate would silently decide that
#: nothing changed.
ROOT = Path(__file__).resolve().parent.parent
LEVELS_PATH = str(store.LEVELS_FILE.relative_to(ROOT))


class Undecidable(Exception):
    """The changes could not be parsed.

    This differs from "nothing changed" exactly as not knowing differs from
    knowing. A gate that takes one for the other lets demotions and crossings of
    the confirmed-evidence boundary through to the main branch, and does it in
    silence.
    """


@dataclass
class Decision:
    """What the parsing came to: whether review is needed, and why."""

    needs_review: bool = False
    reasons: list[str] = field(default_factory=list)
    #: How many level changes were found in all.
    changes: int = 0

    def as_text(self) -> str:
        if not self.changes:
            return "no level changes"
        if not self.needs_review:
            return f"{self.changes} changes, all applied automatically"
        return f"{self.changes} changes, needing review: " + "; ".join(self.reasons)


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else -1


def classify(
    added: list[dict], previous_levels: dict[str, str] | None = None
) -> Decision:
    """Parse the entries added to the level journal.

    `previous_levels` holds the level a technology had before the change. A
    missing entry means the level was computed for the first time; that does not
    count as a promotion from nothing and needs no review.
    """
    previous_levels = previous_levels or {}
    decision = Decision(changes=len(added))

    for entry in added:
        tech = entry.get("technology_id", "?")
        level = entry.get("level", "")
        before = previous_levels.get(tech)

        if entry.get("evidence_basis") == "manual":
            decision.needs_review = True
            decision.reasons.append(f"{tech}: evidence entered by a person")
            continue

        if before is not None and _rank(level) < _rank(before):
            decision.needs_review = True
            decision.reasons.append(f"{tech}: demotion {before} → {level}")
            continue

        if _rank(level) >= _rank(REVIEW_THRESHOLD):
            decision.needs_review = True
            decision.reasons.append(
                f"{tech}: entering {level}, the confirmed-evidence boundary"
            )

    return decision


def added_entries_from_git(repo: Path | None = None) -> list[dict]:
    """The entries appended to the level journal and not yet committed.

    The comparison is against `HEAD` rather than against the index. The
    difference is decisive: a bare `git diff` shows only what is unstaged, so any
    `git add` performed before the gate would hide the changes from it entirely.
    The gate would not fail; it would answer "nothing changed" and let
    everything through to the main branch, demotions included.

    Any inability to parse the difference raises `Undecidable`. It used to turn
    into an empty list, and an empty list means "nothing changed": a missing
    repository, a moved journal, a truncated line and a refusal from git all
    looked equally harmless to the gate.
    """
    # The default is the root of the repository rather than the current
    # directory: the path of the journal is given relative to the root, and a run
    # from a subdirectory would otherwise yield an empty parse instead of a
    # refusal.
    base = Path(repo) if repo is not None else ROOT

    # git does not treat a missing journal as an error: an empty path list is an
    # ordinary thing to it, and `git diff` answers with a zero and nothing. To
    # the gate that is indistinguishable from "nothing changed", so existence is
    # checked outright.
    if not (base / LEVELS_PATH).exists():
        raise Undecidable(f"there is no level journal at {LEVELS_PATH}")

    result = subprocess.run(
        ["git", "diff", "HEAD", "--unified=0", "--", LEVELS_PATH],
        capture_output=True, text=True, cwd=base,
    )
    if result.returncode != 0:
        raise Undecidable(
            f"git did not show the changes to {LEVELS_PATH}: "
            f"{result.stderr.strip()[:200] or 'exit code ' + str(result.returncode)}"
        )

    out: list[dict] = []
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            payload = line[1:].strip()
            if not payload:
                continue
            try:
                out.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise Undecidable(
                    f"a line of the level journal does not parse ({exc}); "
                    f"it begins: {payload[:60]!r}"
                ) from exc
    return out


def previous_levels_before(added: list[dict]) -> dict[str, str]:
    """The levels the technologies had before the added entries.

    The journal is ordered in time, so the previous level is the last one a
    technology had among the entries that are not part of the addition.
    """
    added_keys = {
        (e.get("technology_id"), e.get("level"), e.get("computed_at")) for e in added
    }
    previous: dict[str, str] = {}
    for entry in store.load_levels():
        key = (entry.technology_id, entry.level, entry.computed_at.isoformat())
        if key in added_keys:
            continue
        previous[entry.technology_id] = entry.level
    return previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--github", action="store_true",
        help="print the result as workflow output variables",
    )
    args = parser.parse_args()

    # If it could not be parsed, it goes to a person. The gate fails closed: the
    # price of one review too many is a click, and the price of a missed demotion
    # is a wrong claim about a technology on the main branch.
    #
    # The exit code stays zero deliberately. A non-zero one would stop the job
    # entirely, and the run-log line would not reach the main branch — and on it
    # depend both the sign of activity for the platform and the date of the last
    # check that a reader sees.
    try:
        added = added_entries_from_git()
    except Undecidable as exc:
        sys.stderr.write(f"the changes could not be parsed: {exc}\n")
        if args.github:
            print("review=true")
            print("changes=0")
        else:
            print(f"the changes could not be parsed, review is needed: {exc}")
        return 0

    decision = classify(added, previous_levels_before(added))

    if args.github:
        print(f"review={'true' if decision.needs_review else 'false'}")
        print(f"changes={decision.changes}")
    else:
        print(decision.as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
