"""Сгенерированная схема интерфейса не должна расходиться с декларацией.

Схема измерений объявлена один раз, в `core/dimensions_schema.py`. Интерфейсу
она нужна тоже, и её модуль порождается из той же декларации. Этот тест не даёт
им разойтись: если модуль правили руками или забыли пересобрать после изменения
схемы, он падает.

Расхождение описаний — исходный дефект, ради устранения которого проект
перестраивался; повторять его в новом виде нельзя.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_artifacts import SCHEMA_MODULE, render_schema_module  # noqa: E402


def test_generated_schema_module_matches_declaration():
    assert SCHEMA_MODULE.exists(), (
        "модуль схемы для интерфейса отсутствует; выполните `make artifacts`"
    )
    actual = SCHEMA_MODULE.read_text(encoding="utf-8")
    expected = render_schema_module()
    assert actual == expected, (
        "схема интерфейса разошлась с декларацией; выполните `make artifacts` "
        "и не правьте сгенерированный модуль вручную"
    )


def test_locale_files_have_no_broken_characters():
    """Символ замены в переводе — след испорченной записи файла.

    Отказ тихий: строка отображается почти правильно, и заметить подмену одной
    буквы можно только вычитыванием. Один такой случай уже был.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for lang in ("ru", "en"):
        path = root / "ui" / "src" / "i18n" / f"{lang}.json"
        text = path.read_text(encoding="utf-8")
        assert "�" not in text, f"{lang}.json: испорченные символы в переводе"
        json.loads(text)  # файл обязан оставаться разбираемым


def test_locales_declare_the_same_keys():
    """Ключ, добавленный в один язык и забытый в другом, показывает читателю код."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    def flat(node: object, prefix: str = "") -> set[str]:
        if isinstance(node, dict):
            out: set[str] = set()
            for key, value in node.items():
                out |= flat(value, f"{prefix}.{key}")
            return out
        return {prefix}

    ru = flat(json.loads((root / "ui" / "src" / "i18n" / "ru.json").read_text(encoding="utf-8")))
    en = flat(json.loads((root / "ui" / "src" / "i18n" / "en.json").read_text(encoding="utf-8")))
    assert ru == en, (
        f"только в русском: {sorted(ru - en)}; только в английском: {sorted(en - ru)}"
    )
