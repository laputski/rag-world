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
