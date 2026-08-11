"""Перечень мутаций не должен гнить между прогонами.

Мутационный прогон идёт двадцать с лишним минут, поэтому запускается отдельно,
а не при каждой правке. Отсюда опасность: код меняется, образец записи
перестаёт совпадать, и запись тихо перестаёт что-либо проверять. Перечень при
этом выглядит внушительно и остаётся зелёным, потому что его никто не запускал.

За один день такое случилось трижды, поэтому целостность перечня проверяется
здесь, в обычном наборе. Проверка мгновенная: она не запускает ни одного
мутанта, а только сверяет, что каждому есть куда примениться.

Разделение намеренное. Дорогое (сам прогон) идёт по расписанию, дешёвое
(годность перечня) — при каждой правке, потому что портится именно от правок.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mutate  # noqa: E402


@pytest.mark.parametrize(
    "mutation", mutate.MUTATIONS, ids=lambda m: f"{m.path}::{m.rule}"
)
def test_every_mutation_still_applies(mutation):
    """Образец записи по-прежнему встречается в коде, который она сторожит."""
    target = ROOT / mutation.path
    assert target.exists(), f"файл {mutation.path} не существует"
    source = target.read_text(encoding="utf-8")
    assert mutation.before in source, (
        f"образец записи «{mutation.rule}» больше не встречается в "
        f"{mutation.path}. Запись ничего не проверяет, оставаясь в перечне и "
        "создавая видимость охраны: поправьте образец или уберите запись."
    )


@pytest.mark.parametrize(
    "mutation", mutate.MUTATIONS, ids=lambda m: f"{m.path}::{m.rule}"
)
def test_every_mutation_actually_changes_something(mutation):
    """Порча обязана менять код, иначе прогон проверяет пустоту."""
    assert mutation.before != mutation.after, f"«{mutation.rule}» ничего не меняет"
    source = (ROOT / mutation.path).read_text(encoding="utf-8")
    assert source.replace(mutation.before, mutation.after, 1) != source


def test_rules_are_named_distinctly():
    """Одинаковые имена делают отчёт нечитаемым: непонятно, что именно выжило."""
    names = [m.rule for m in mutate.MUTATIONS]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"повторяющиеся имена правил: {duplicates}"


def test_catalogue_covers_the_load_bearing_modules():
    """Перечень охватывает то, на чём держится автономный проход.

    Список короткий и намеренно неполный: он называет места, отсутствие
    которых в перечне означало бы, что прогон не смотрит на главное.
    """
    covered = {m.path for m in mutate.MUTATIONS}
    for path in (
        "core/maturity.py",
        "scripts/validate_data.py",
        "scripts/classify_changes.py",
        "scripts/make_release.py",
        "scripts/check_links.py",
        "services/registry/store.py",
    ):
        assert path in covered, f"{path} не охвачен ни одной мутацией"


# ─── Сам прогон ──────────────────────────────────────────────────────────────


def test_absent_pattern_is_reported_not_skipped(tmp_path, monkeypatch):
    """Неприменившийся мутант отличается от пойманного и от выжившего.

    Пропуск выглядел бы как успех, а это ровно тот случай, ради которого
    существует проверка выше.
    """
    sample = tmp_path / "sample.py"
    sample.write_text("значение = 1\n", encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    absent = mutate.Mutation("sample.py", "чего нет", "такого текста нет", "иное")
    assert mutate.survives(absent) is None


def test_file_is_restored_even_when_the_run_blows_up(tmp_path, monkeypatch):
    """Порча не должна пережить прогон ни при каком исходе.

    Прерывание с клавиатуры посреди прогона иначе оставило бы испорченный
    боевой код в рабочем дереве.
    """
    sample = tmp_path / "sample.py"
    original = "значение = 1\n"
    sample.write_text(original, encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    def boom():
        raise KeyboardInterrupt

    monkeypatch.setattr(mutate, "_pytest", boom)
    with pytest.raises(KeyboardInterrupt):
        mutate.survives(mutate.Mutation("sample.py", "правило", "1", "2"))

    assert sample.read_text(encoding="utf-8") == original
