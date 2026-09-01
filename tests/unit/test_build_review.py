"""The guard over the justifications, and the case it did not have.

A justification that has drifted from the registry is worse than none: it
explains a value that is not there, and it does so convincingly, so the reader
sees coherent reasoning and does not think to check it. That is what `check`
exists to catch.

The guard knew three kinds of justification: one for a value, one for a
dimension marked inapplicable, and one for a residual. It lacked a fourth, and
the lack showed the first time a source described what a component does while
withholding how it does it. Such a dimension carries no value, and the reason
for the emptiness belongs beside it; the guard, having no case for it, called
the note a drift.

The three states are different assertions and must not collapse into one. A
value says the source states it. An inapplicability says the dimension asserts
nothing about this object. An unstated dimension says the source was read and is
silent. A registry that cannot tell the second from the third would show "does
not apply" where the truth is "nobody told us".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_review  # noqa: E402

from services.registry import store  # noqa: E402


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """An empty registry in a directory of its own."""
    for name, path in (
        ("DATA_DIR", tmp_path),
        ("TECHNOLOGIES_DIR", tmp_path / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "evidence"),
        ("METRICS_DIR", tmp_path / "metrics"),
        ("LEVELS_FILE", tmp_path / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", tmp_path / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    (tmp_path / "technologies").mkdir(parents=True)
    return tmp_path


def save(**overrides) -> store.Technology:
    payload = {
        "id": "alpha", "name": "Alpha", "kind": "architecture", "groups": ["A"],
        "configuration": {"A4": "graph"},
    }
    payload.update(overrides)
    tech = store.Technology(**payload)
    store.save_technology(tech)
    return tech


def note(**overrides) -> dict:
    row = {"technology_id": "alpha", "code": "A4", "to": "graph",
           "did": "…", "why": "…", "source": "…"}
    row.update(overrides)
    return row


def complains_about(fragment: str, problems: list[str]) -> bool:
    return any(fragment in problem for problem in problems)


# ─── The case that was missing: a dimension the source does not state ────────


def test_a_note_on_an_unstated_dimension_draws_no_complaint(registry):
    """The other side: an explained absence is not a drift."""
    save(configuration={"A4": "graph"})
    problems = build_review.check([note(code="C2", to=None, unstated=True)])
    assert problems == [], problems


def test_a_note_calling_a_valued_dimension_unstated_is_caught(registry):
    """The note would say the source is silent where the registry holds a value."""
    save(configuration={"A4": "graph", "C2": "single_shot"})
    problems = build_review.check([note(code="C2", to=None, unstated=True)])
    assert complains_about("the registry holds", problems), problems


def test_a_note_calling_an_inapplicable_dimension_unstated_is_caught(registry):
    """"Does not apply" and "nobody told us" are different assertions."""
    save(configuration={"A4": "graph"}, configuration_inapplicable=["E1"])
    problems = build_review.check([note(code="E1", to=None, unstated=True)])
    assert complains_about("marked inapplicable", problems), problems


def test_an_unmarked_note_without_a_value_is_still_caught(registry):
    """The mark is what distinguishes an explained absence from a stale note.

    Without this the new case would amount to accepting every note whose value
    has gone, which is the drift the guard was written for.
    """
    save(configuration={"A4": "graph"})
    problems = build_review.check([note(code="C2", to="single_shot")])
    assert complains_about("the value is not in the registry", problems), problems


# ─── The cases the guard already had, which must survive ─────────────────────


def test_a_note_written_for_another_value_is_caught(registry):
    save(configuration={"A4": "tree"})
    problems = build_review.check([note(code="A4", to="graph")])
    assert complains_about("the justification is written for", problems), problems


def test_a_disagreeing_mark_for_a_run_time_choice_is_caught(registry):
    save(configuration={"A4": "graph"}, configuration_variable=["A4"])
    problems = build_review.check([note(code="A4", to="graph")])
    assert complains_about("the mark for a run-time choice", problems), problems


def test_a_note_for_a_residual_the_record_does_not_carry_is_caught(registry):
    save(configuration={"A4": "graph"}, residual=[])
    problems = build_review.check(
        [{"technology_id": "alpha", "residual": "synonymy_edges", "did": "…"}]
    )
    assert complains_about("which the record does not carry", problems), problems


def test_sound_justifications_draw_no_complaint(registry):
    """A guard that cries over correct data stops being a guard."""
    save(
        configuration={"A4": "graph", "B1": "hyde"},
        configuration_variable=["B1"],
        configuration_inapplicable=["E1"],
        residual=["synonymy_edges"],
    )
    problems = build_review.check([
        note(code="A4", to="graph"),
        note(code="B1", to="hyde", variable=True),
        note(code="E1", to=None, inapplicable=True),
        note(code="C2", to=None, unstated=True),
        {"technology_id": "alpha", "residual": "synonymy_edges", "did": "…"},
    ])
    assert problems == [], problems


def test_the_page_names_the_kind_of_every_justification(registry):
    """A row without a label reads as an unexplained mark."""
    tech = save(configuration={"A4": "graph"})
    kind = build_review._kind(note(code="C2", to=None, unstated=True), tech)
    assert kind in build_review.KIND_LABEL, kind
