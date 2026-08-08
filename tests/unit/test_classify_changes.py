"""Тесты классификации изменений реестра.

Правило решает, что бот применит сам, а что покажет человеку. Ошибка в нём
проявляется двумя способами, и оба плохи: либо через просмотр проходит всё и он
вырождается в формальность, либо мимо просмотра проходит понижение уровня, и
портал молча меняет утверждение о технологии.

Раньше это правило жило внутри описания задания и тестами не покрывалось вовсе.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.classify_changes import (  # noqa: E402
    REVIEW_THRESHOLD,
    classify,
)


def entry(tech: str, level: str, basis: str = "computed") -> dict:
    return {
        "technology_id": tech,
        "level": level,
        "evidence_basis": basis,
        "computed_at": "2026-08-08",
    }


# ─── Применяется само ────────────────────────────────────────────────────────


def test_no_changes_needs_no_review():
    decision = classify([])
    assert decision.needs_review is False
    assert decision.changes == 0
    assert "нет" in decision.as_text()


def test_first_computed_level_applies_itself():
    """Уровень вычислен впервые: повышением с пустого места это не считается."""
    decision = classify([entry("demo", "L1")], previous_levels={})
    assert decision.needs_review is False


def test_promotion_within_lower_levels_applies_itself():
    decision = classify([entry("demo", "L2")], {"demo": "L1"})
    assert decision.needs_review is False


def test_promotion_to_l3_applies_itself():
    """L3 ещё не граница: это наличие собираемого кода, проверяемое машиной."""
    decision = classify([entry("demo", "L3")], {"demo": "L2"})
    assert decision.needs_review is False


# ─── Требует просмотра ───────────────────────────────────────────────────────


def test_downgrade_requires_review():
    decision = classify([entry("demo", "L1")], {"demo": "L3"})
    assert decision.needs_review is True
    assert any("понижение" in r for r in decision.reasons)


def test_crossing_confirmation_boundary_requires_review():
    decision = classify([entry("demo", REVIEW_THRESHOLD)], {"demo": "L3"})
    assert decision.needs_review is True
    assert any("граница" in r for r in decision.reasons)


def test_levels_above_boundary_require_review():
    for level in ("L4", "L5", "L6"):
        decision = classify([entry("demo", level)], {"demo": "L3"})
        assert decision.needs_review is True, level


def test_manual_evidence_requires_review():
    """Ручное свидетельство в автоматическом проходе означает правку файла."""
    decision = classify([entry("demo", "L2", basis="manual")], {"demo": "L1"})
    assert decision.needs_review is True
    assert any("человеком" in r for r in decision.reasons)


def test_manual_basis_wins_over_level():
    """Ручное свидетельство показывается даже на низком уровне."""
    decision = classify([entry("demo", "L1", basis="manual")], {})
    assert decision.needs_review is True


# ─── Разбор пачки ────────────────────────────────────────────────────────────


def test_one_suspicious_change_marks_whole_batch():
    decision = classify(
        [entry("a", "L2"), entry("b", "L1"), entry("c", "L2")],
        {"a": "L1", "b": "L3", "c": "L1"},
    )
    assert decision.needs_review is True
    assert decision.changes == 3
    assert len(decision.reasons) == 1, "причина указывается только для виновника"


def test_all_ordinary_changes_apply_themselves():
    decision = classify(
        [entry("a", "L2"), entry("b", "L1"), entry("c", "L3")],
        {"a": "L1", "b": None if False else "L0", "c": "L2"},
    )
    assert decision.needs_review is False
    assert decision.changes == 3


def test_unknown_level_does_not_crash():
    """Испорченная запись не должна ронять проход перед самой фиксацией."""
    decision = classify([{"technology_id": "demo", "level": "L9"}], {"demo": "L1"})
    assert isinstance(decision.needs_review, bool)


def test_summary_text_mentions_count():
    decision = classify([entry("a", "L2")], {"a": "L1"})
    assert "1" in decision.as_text()
