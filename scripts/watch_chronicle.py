#!/usr/bin/env python3
"""The watch over a chronicle that has stopped moving.

The level journal grows only when a level changes, which is what makes it a
chronicle rather than a log of runs. The same property hides a failure. A pass
that collects evidence week after week and never moves a level looks exactly
like a pass that collects nothing, and both look exactly like a registry that
has simply settled.

Three readings, one appearance:

* the registry has saturated, and the arriving evidence repeats types already
  recorded, which is the ordinary state of a mature record;
* the records lack the very links from which the missing evidence would be
  collected, so a level that could rise has no route by which to rise;
* a source has been refusing for a month and nobody noticed.

This watch tells none of the three apart, and it is not built to. It asserts one
checkable thing: the chronicle has not moved while the passes kept bringing
evidence. That is the condition under which the question is worth asking, and
until it is asked out loud the silence reads as normality.

The observation is made **on the journal itself** rather than on the
`levels_changed` figure of the run log. The figure is the log's account of a
pass; the journal is the thing the account is about, and the two have diverged
already: two entries dated 2026-08-14 were written by hand, while the pass of
that same day recorded that it had changed nothing.

Usage::

    python3 scripts/watch_chronicle.py
    python3 scripts/watch_chronicle.py --quiet-passes 5
    python3 scripts/watch_chronicle.py --fail    # exit 1 when the watch sounds
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: How many passes in a row may leave the chronicle untouched before the watch
#: sounds. Two is an ordinary fortnight, in which nothing happening is expected.
#: Three is a month of collection over a scale that never moved: long enough to
#: be worth a look, and short enough that the platform still keeps the run logs
#: in which the answer would be found.
DEFAULT_QUIET_PASSES = 3


@dataclass(frozen=True)
class Silence:
    """A chronicle that has not moved while the passes kept bringing evidence."""

    #: How many passes ran after the last entry of the chronicle.
    passes: int
    #: How much evidence those passes added between them.
    evidence_added: int
    #: The date of the last entry of the chronicle, or None when it is empty.
    since: date | None
    #: The date of the last of the silent passes.
    latest_run: date | None

    def message(self) -> str:
        since = self.since.isoformat() if self.since else "no entry ever"
        latest = self.latest_run.isoformat() if self.latest_run else "never"
        return (
            f"the chronicle has not moved since {since}: {self.passes} passes "
            f"up to {latest} added {self.evidence_added} pieces of evidence "
            f"between them and changed no level"
        )


def look(
    runs: list[store.CollectionRun],
    levels: list[store.LevelEntry],
    *,
    quiet_passes: int = DEFAULT_QUIET_PASSES,
) -> Silence | None:
    """Whether the chronicle has been silent while evidence kept arriving.

    Returns the silence when the watch sounds and None when it does not. It is
    a pure function of the two journals: nothing is read from the clock, so the
    same pair of journals always yields the same verdict.
    """
    if quiet_passes < 1:
        raise ValueError(
            "a watch that sounds after no passes at all watches nothing"
        )

    newest_entry = max((entry.computed_at for entry in levels), default=None)
    # A pass on the very day of an entry is not counted as silent: it is either
    # the pass the entry came out of or one that ran beside it, and calling it
    # silent would accuse the chronicle of missing what it recorded.
    quiet = [
        run for run in runs if newest_entry is None or run.ran_at > newest_entry
    ]
    gathered = sum(run.evidence_added for run in quiet)

    if len(quiet) < quiet_passes:
        return None
    # Passes that brought nothing assert "nobody found anything", which is a
    # different statement and none of this watch's business: a scale that does
    # not move over evidence that never arrived is exactly what should happen.
    if gathered <= 0:
        return None

    return Silence(
        passes=len(quiet),
        evidence_added=gathered,
        since=newest_entry,
        latest_run=max((run.ran_at for run in quiet), default=None),
    )


def run(*, quiet_passes: int = DEFAULT_QUIET_PASSES) -> Silence | None:
    """The watch over the registry on disk."""
    return look(store.load_runs(), store.load_levels(), quiet_passes=quiet_passes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quiet-passes", type=int, default=DEFAULT_QUIET_PASSES,
        help="how many passes in a row may change nothing before the watch sounds",
    )
    parser.add_argument(
        "--fail", action="store_true",
        help="end with an error when the watch sounds",
    )
    args = parser.parse_args()

    silence = run(quiet_passes=args.quiet_passes)
    if silence is None:
        print(
            "the chronicle is moving, or the passes brought nothing to move it"
        )
        return 0
    print(silence.message())
    return 1 if args.fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
