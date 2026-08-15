"""Tests of the classification of registry changes.

The rule decides what the bot applies itself and what it shows to a person. An
error shows in two ways, and both are bad: either review is flooded until it
degenerates into a formality, or a demotion slips past review and the portal
silently changes a claim about a technology.

This rule used to live inside a job description and was covered by no test.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.classify_changes import (  # noqa: E402
    LEVELS_PATH,
    REVIEW_THRESHOLD,
    Undecidable,
    added_entries_from_git,
    classify,
)
from services.registry import store  # noqa: E402


def entry(tech: str, level: str, basis: str = "computed") -> dict:
    return {
        "technology_id": tech,
        "level": level,
        "evidence_basis": basis,
        "computed_at": "2026-08-08",
    }


def journal_line(tech: str, level: str, when: str, basis: str = "computed") -> str:
    return json.dumps({
        "technology_id": tech, "level": level, "confidence": 1.0,
        "rule_version": "1.0.0", "computed_at": when,
        "evidence_snapshot": [], "evidence_basis": basis,
    }, ensure_ascii=False)


@pytest.fixture
def repo(tmp_path):
    """A repository with the level journal already committed."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    journal = tmp_path / LEVELS_PATH
    journal.parent.mkdir(parents=True)
    journal.write_text(journal_line("alpha", "L0", "2026-08-01") + "\n",
                       encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "j"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


def append(repo: Path, line: str) -> None:
    with (repo / LEVELS_PATH).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ─── Applied automatically ───────────────────────────────────────────────────


def test_no_changes_needs_no_review():
    decision = classify([])
    assert decision.needs_review is False
    assert decision.changes == 0
    assert "no level changes" in decision.as_text()


def test_first_computed_level_applies_itself():
    """A level computed for the first time is not a promotion from nothing."""
    decision = classify([entry("demo", "L1")], previous_levels={})
    assert decision.needs_review is False


def test_promotion_within_lower_levels_applies_itself():
    decision = classify([entry("demo", "L2")], {"demo": "L1"})
    assert decision.needs_review is False


def test_promotion_to_l3_applies_itself():
    """L3 is not yet the boundary: it is buildable code, checkable by a machine."""
    decision = classify([entry("demo", "L3")], {"demo": "L2"})
    assert decision.needs_review is False


# ─── Needs review ────────────────────────────────────────────────────────────


def test_downgrade_requires_review():
    decision = classify([entry("demo", "L1")], {"demo": "L3"})
    assert decision.needs_review is True
    assert any("demotion" in r for r in decision.reasons)


def test_crossing_confirmation_boundary_requires_review():
    decision = classify([entry("demo", REVIEW_THRESHOLD)], {"demo": "L3"})
    assert decision.needs_review is True
    assert any("confirmed-evidence boundary" in r for r in decision.reasons)


def test_levels_above_boundary_require_review():
    for level in ("L4", "L5", "L6"):
        decision = classify([entry("demo", level)], {"demo": "L3"})
        assert decision.needs_review is True, level


def test_manual_evidence_requires_review():
    """Manual evidence in an automatic pass means somebody edited the file."""
    decision = classify([entry("demo", "L2", basis="manual")], {"demo": "L1"})
    assert decision.needs_review is True
    assert any("entered by a person" in r for r in decision.reasons)


def test_manual_basis_wins_over_level():
    """Manual evidence is shown even at a low level."""
    decision = classify([entry("demo", "L1", basis="manual")], {})
    assert decision.needs_review is True


# ─── A batch ─────────────────────────────────────────────────────────────────


def test_one_suspicious_change_marks_whole_batch():
    decision = classify(
        [entry("a", "L2"), entry("b", "L1"), entry("c", "L2")],
        {"a": "L1", "b": "L3", "c": "L1"},
    )
    assert decision.needs_review is True
    assert decision.changes == 3
    assert len(decision.reasons) == 1, "a reason is given only for the culprit"


def test_all_ordinary_changes_apply_themselves():
    decision = classify(
        [entry("a", "L2"), entry("b", "L1"), entry("c", "L3")],
        {"a": "L1", "b": None if False else "L0", "c": "L2"},
    )
    assert decision.needs_review is False
    assert decision.changes == 3


def test_unknown_level_does_not_crash():
    """A spoiled entry must not crash the pass just before the commit."""
    decision = classify([{"technology_id": "demo", "level": "L9"}], {"demo": "L1"})
    assert isinstance(decision.needs_review, bool)


def test_summary_text_mentions_count():
    decision = classify([entry("a", "L2")], {"a": "L1"})
    assert "1" in decision.as_text()


# ─── Parsing the diff: what feeds the rule ───────────────────────────────────
#
# The rule itself was well covered while the parsing that feeds it was not covered
# at all. Meanwhile an empty list means "nothing changed", and any inability to
# parse the diff turned into permission to apply everything.


def test_appended_entries_are_read(repo):
    append(repo, journal_line("alpha", "L2", "2026-08-11"))
    assert [e["level"] for e in added_entries_from_git(repo=repo)] == ["L2"]


def test_staged_change_is_still_seen(repo):
    """A change that has been staged must still be visible to the gate.

    A bare `git diff` shows only what is unstaged. While the comparison worked that
    way, any `git add` before the gate hid the whole transition from it, and the
    rule received emptiness instead of a change.
    """
    append(repo, journal_line("alpha", "L4", "2026-08-11"))
    subprocess.run(["git", "add", LEVELS_PATH], cwd=repo, check=True,
                   capture_output=True)

    added = added_entries_from_git(repo=repo)
    assert [e["level"] for e in added] == ["L4"]
    assert classify(added, {"alpha": "L0"}).needs_review is True


def test_not_a_repository_is_undecidable(tmp_path):
    """The journal is there and version control is not: the diff cannot be parsed."""
    journal = tmp_path / LEVELS_PATH
    journal.parent.mkdir(parents=True)
    journal.write_text(journal_line("alpha", "L4", "2026-08-11") + "\n",
                       encoding="utf-8")
    with pytest.raises(Undecidable, match="git"):
        added_entries_from_git(repo=tmp_path)


def test_missing_journal_is_undecidable(tmp_path):
    """The journal moved and the parsing looks at the old path.

    git does not treat a missing path as an error and answers with a zero and
    nothing. To the gate that is indistinguishable from "nothing changed", so
    existence is checked outright rather than inferred from git's silence.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "readme").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    with pytest.raises(Undecidable, match="no level journal"):
        added_entries_from_git(repo=tmp_path)


def test_half_written_line_is_undecidable(repo):
    """A truncated line is not passed over in silence.

    A pass can be interrupted in the middle of an entry. Skipping such a line means
    not seeing the level change written in it.
    """
    with (repo / LEVELS_PATH).open("a", encoding="utf-8") as fh:
        fh.write('{"technology_id": "alpha", "level": "L4", "rule_ver')
    with pytest.raises(Undecidable):
        added_entries_from_git(repo=repo)


# ─── The gate fails closed ───────────────────────────────────────────────────


def _gate_output(monkeypatch, capsys, raises: Exception | None = None) -> str:
    from scripts import classify_changes

    if raises is not None:
        def boom(repo=None):
            raise raises
        monkeypatch.setattr(classify_changes, "added_entries_from_git", boom)
    monkeypatch.setattr(sys, "argv", ["classify_changes.py", "--github"])
    code = classify_changes.main()
    assert code == 0, (
        "a non-zero code would stop the job and the mark of the pass would not "
        "reach the main branch"
    )
    return capsys.readouterr().out


def test_gate_asks_for_review_when_it_cannot_tell(monkeypatch, capsys):
    """Not knowing counts as "show it to a person", not as "nothing changed".

    The price of one review too many is a click. The price of a missed demotion is
    a wrong claim about a technology on the main branch.
    """
    out = _gate_output(monkeypatch, capsys, raises=Undecidable("git says nothing"))
    assert "review=true" in out


def test_gate_applies_itself_on_ordinary_changes(monkeypatch, capsys):
    """The other side: an ordinary change must not demand review."""
    from scripts import classify_changes

    monkeypatch.setattr(classify_changes, "added_entries_from_git", lambda repo=None: [])
    monkeypatch.setattr(classify_changes, "previous_levels_before", lambda added: {})
    out = _gate_output(monkeypatch, capsys)
    assert "review=false" in out


def test_journal_path_follows_the_store(repo):
    """The path comes from the store rather than being written out.

    A divergence would cost silence: the parsing would look at a file that does not
    exist and report that nothing changed.
    """
    assert store.LEVELS_FILE == ROOT / LEVELS_PATH
