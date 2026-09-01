"""The watch over a silent chronicle, and the decoys it has to catch.

A guard that is only ever shown healthy data proves nothing: it stays green
because there was nothing to catch, and the day its condition breaks it stays
green for the same reason. So a violation is built here for the watch to find,
and the other side is checked too — a watch that cries over an ordinary week
stops being read, and the alarm that matters is lost among the ones that do not.

The condition being watched is narrow on purpose: the chronicle has not moved
while the passes kept bringing evidence. Everything else — why it has not moved,
whether that is right — is a question for a person, and the watch exists to make
sure the question gets asked.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import watch_chronicle  # noqa: E402

from services.registry import store  # noqa: E402


def a_pass(day: str, *, evidence: int = 10, levels: int = 0) -> store.CollectionRun:
    """A pass of the collection, as the run log records it."""
    return store.CollectionRun(
        ran_at=date.fromisoformat(day),
        sources=["arxiv", "openalex", "github"],
        evidence_added=evidence,
        levels_changed=levels,
        data_changed=bool(evidence or levels),
    )


def an_entry(day: str, technology_id: str = "alpha", level: str = "L2"):
    """An entry of the chronicle: a level that changed on that day."""
    return store.LevelEntry(
        technology_id=technology_id,
        level=level,
        confidence=1.0,
        evidence_basis="computed",
        rule_version="1.0.0",
        computed_at=date.fromisoformat(day),
    )


# ─── The decoys: what the watch must catch ───────────────────────────────────


def test_three_silent_passes_over_arriving_evidence_sound_the_watch():
    """The case the watch was built for, in the shape it actually occurred in.

    Three weekly passes after the last entry of the chronicle, eighty-six
    pieces of evidence between them, and a scale that did not move once.
    """
    silence = watch_chronicle.look(
        [
            a_pass("2026-08-14", evidence=36),
            a_pass("2026-08-17", evidence=26),
            a_pass("2026-08-24", evidence=27),
            a_pass("2026-08-31", evidence=33),
        ],
        [an_entry("2026-08-14")],
    )
    assert silence is not None, "three silent passes must sound the watch"
    assert silence.passes == 3, "the pass of the day of the entry is not silent"
    assert silence.evidence_added == 26 + 27 + 33
    assert silence.since == date(2026, 8, 14)
    assert silence.latest_run == date(2026, 8, 31)


def test_a_chronicle_that_never_had_an_entry_is_watched_too():
    """An empty journal is the strongest form of the same condition.

    Reading it as "there is nothing to compare against, so keep quiet" would
    leave a registry that never computed a level at all entirely unwatched.
    """
    silence = watch_chronicle.look(
        [a_pass("2026-08-17"), a_pass("2026-08-24"), a_pass("2026-08-31")],
        [],
    )
    assert silence is not None
    assert silence.passes == 3
    assert silence.since is None
    assert "no entry ever" in silence.message()


def test_the_message_names_the_dates_and_the_evidence():
    """An alarm without its terms asks to be trusted, and there is nothing to trust."""
    silence = watch_chronicle.look(
        [a_pass("2026-08-17", evidence=26), a_pass("2026-08-24", evidence=27),
         a_pass("2026-08-31", evidence=33)],
        [an_entry("2026-08-14")],
    )
    assert silence is not None
    message = silence.message()
    assert "2026-08-14" in message
    assert "2026-08-31" in message
    assert "86" in message
    assert "3 passes" in message


# ─── The other side: an ordinary week must not sound the watch ───────────────


def test_a_chronicle_that_moved_keeps_the_watch_quiet():
    """A guard that cries over correct data stops being a guard."""
    silence = watch_chronicle.look(
        [
            a_pass("2026-08-10"),
            a_pass("2026-08-17"),
            a_pass("2026-08-24", levels=2),
            a_pass("2026-08-31"),
        ],
        [an_entry("2026-08-24")],
    )
    assert silence is None, "one pass since the last entry is not a silence"


def test_two_quiet_passes_are_an_ordinary_fortnight():
    """The threshold is what separates a quiet fortnight from a stalled month."""
    runs = [a_pass("2026-08-24"), a_pass("2026-08-31")]
    assert watch_chronicle.look(runs, [an_entry("2026-08-14")]) is None
    # The same two passes with the threshold lowered do sound it: the boundary
    # is the parameter's and not an accident of the data.
    assert watch_chronicle.look(
        runs, [an_entry("2026-08-14")], quiet_passes=2
    ) is not None


def test_passes_that_brought_nothing_do_not_sound_the_watch():
    """"Nobody found anything" is a different statement, and a legitimate one.

    A scale that does not move over evidence that never arrived is exactly what
    should happen; sounding the alarm there would accuse the rule of a failure
    belonging to the sources.
    """
    silence = watch_chronicle.look(
        [
            a_pass("2026-08-17", evidence=0),
            a_pass("2026-08-24", evidence=0),
            a_pass("2026-08-31", evidence=0),
        ],
        [an_entry("2026-08-14")],
    )
    assert silence is None


def test_passes_before_the_last_entry_are_not_counted():
    """The streak is the passes since the chronicle last moved, not all of them."""
    silence = watch_chronicle.look(
        [
            a_pass("2026-08-01"),
            a_pass("2026-08-08"),
            a_pass("2026-08-14", levels=2),
            a_pass("2026-08-31"),
        ],
        [an_entry("2026-08-14")],
    )
    assert silence is None, "the four passes are one silent pass and three older ones"


def test_the_newest_entry_governs_even_when_the_journal_is_out_of_order():
    """The journal is append-only but not sorted by the day a level was computed."""
    silence = watch_chronicle.look(
        [a_pass("2026-08-17"), a_pass("2026-08-24"), a_pass("2026-08-31")],
        [an_entry("2026-08-24"), an_entry("2026-08-09", "beta", "L1")],
    )
    assert silence is None, "the entry of 24 August leaves one silent pass, not three"


# ─── The watch itself has to be answerable ───────────────────────────────────


def test_a_threshold_of_zero_is_refused():
    """A watch that sounds after no passes at all watches nothing."""
    with pytest.raises(ValueError):
        watch_chronicle.look([a_pass("2026-08-31")], [], quiet_passes=0)


def test_the_verdict_is_a_function_of_the_journals_alone():
    """No clock is read: the same pair of journals always yields the same verdict."""
    runs = [a_pass("2026-08-17"), a_pass("2026-08-24"), a_pass("2026-08-31")]
    levels = [an_entry("2026-08-14")]
    first = watch_chronicle.look(runs, levels)
    second = watch_chronicle.look(runs, levels)
    assert first == second
