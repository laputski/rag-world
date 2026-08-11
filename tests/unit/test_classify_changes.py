"""Тесты классификации изменений реестра.

Правило решает, что бот применит сам, а что покажет человеку. Ошибка в нём
проявляется двумя способами, и оба плохи: либо через просмотр проходит всё и он
вырождается в формальность, либо мимо просмотра проходит понижение уровня, и
портал молча меняет утверждение о технологии.

Раньше это правило жило внутри описания задания и тестами не покрывалось вовсе.
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
    """Репозиторий с зафиксированным журналом уровней."""
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


# ─── Разбор различий: то, чем кормится правило ───────────────────────────────
#
# Само правило было покрыто хорошо, а разбор, который его кормит, не покрыт
# вовсе. Между тем пустой список значит «изменений нет», и любая невозможность
# разобрать различия превращалась в разрешение применить всё без просмотра.


def test_appended_entries_are_read(repo):
    append(repo, journal_line("alpha", "L2", "2026-08-11"))
    assert [e["level"] for e in added_entries_from_git(repo=repo)] == ["L2"]


def test_staged_change_is_still_seen(repo):
    """Изменение, попавшее в индекс, шлюз обязан видеть.

    `git diff` без указания показывает только непроиндексированное. Пока
    сравнение шло так, любой `git add` до шлюза скрывал от него переход в L4
    целиком, и правило получало пустоту вместо изменения.
    """
    append(repo, journal_line("alpha", "L4", "2026-08-11"))
    subprocess.run(["git", "add", LEVELS_PATH], cwd=repo, check=True,
                   capture_output=True)

    added = added_entries_from_git(repo=repo)
    assert [e["level"] for e in added] == ["L4"]
    assert classify(added, {"alpha": "L0"}).needs_review is True


def test_not_a_repository_is_undecidable(tmp_path):
    """Журнал на месте, а системы версий нет: разобрать различия нечем."""
    journal = tmp_path / LEVELS_PATH
    journal.parent.mkdir(parents=True)
    journal.write_text(journal_line("alpha", "L4", "2026-08-11") + "\n",
                       encoding="utf-8")
    with pytest.raises(Undecidable, match="git"):
        added_entries_from_git(repo=tmp_path)


def test_missing_journal_is_undecidable(tmp_path):
    """Журнал переехал, а разбор смотрит на прежний путь.

    Отсутствие пути git ошибкой не считает и отвечает нулём с пустотой. Для
    шлюза это неотличимо от «изменений нет», поэтому существование журнала
    проверяется прямо, а не выводится из молчания git.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "readme").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    with pytest.raises(Undecidable, match="журнала уровней нет"):
        added_entries_from_git(repo=tmp_path)


def test_half_written_line_is_undecidable(repo):
    """Оборванная строка не пропускается молча.

    Проход можно прервать на середине записи. Пропустить такую строку значит
    не увидеть изменения уровня, которое в ней записано.
    """
    with (repo / LEVELS_PATH).open("a", encoding="utf-8") as fh:
        fh.write('{"technology_id": "alpha", "level": "L4", "rule_ver')
    with pytest.raises(Undecidable):
        added_entries_from_git(repo=repo)


# ─── Отказ закрытый ──────────────────────────────────────────────────────────


def _gate_output(monkeypatch, capsys, raises: Exception | None = None) -> str:
    from scripts import classify_changes

    if raises is not None:
        def boom(repo=None):
            raise raises
        monkeypatch.setattr(classify_changes, "added_entries_from_git", boom)
    monkeypatch.setattr(sys, "argv", ["classify_changes.py", "--github"])
    code = classify_changes.main()
    assert code == 0, (
        "ненулевой код остановил бы задание, и отметка о прогоне не попала бы "
        "в основную ветку"
    )
    return capsys.readouterr().out


def test_gate_asks_for_review_when_it_cannot_tell(monkeypatch, capsys):
    """Незнание приравнивается к «показать человеку», а не к «изменений нет».

    Цена лишнего просмотра равна одному щелчку. Цена пропущенного понижения
    равна неверному утверждению о технологии в основной ветке.
    """
    out = _gate_output(monkeypatch, capsys, raises=Undecidable("git молчит"))
    assert "review=true" in out


def test_gate_applies_itself_on_ordinary_changes(monkeypatch, capsys):
    """Обратная сторона: обычное изменение не должно требовать просмотра."""
    from scripts import classify_changes

    monkeypatch.setattr(classify_changes, "added_entries_from_git", lambda repo=None: [])
    monkeypatch.setattr(classify_changes, "previous_levels_before", lambda added: {})
    out = _gate_output(monkeypatch, capsys)
    assert "review=false" in out


def test_journal_path_follows_the_store(repo):
    """Путь берётся у хранилища, а не пишется строкой.

    Расхождение обошлось бы молчанием: разбор смотрел бы в несуществующий файл
    и сообщал, что изменений нет.
    """
    assert store.LEVELS_FILE == ROOT / LEVELS_PATH
