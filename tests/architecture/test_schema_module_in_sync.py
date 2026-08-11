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


#: Ключи, где тире отделяет обозначение от расшифровки, а не заменяет связку.
#: «L0 — гипотеза» это словарная статья, а не предложение.
DASH_AS_LABEL = ("level.", "levelCondition.")


def test_dash_does_not_stand_in_for_a_verb():
    """В русских текстах для читателя связка называется словом.

    Тире прячет отношение между частями фразы: читателю приходится самому
    достраивать, перечисление это, причина или определение. Портал объясняет
    непростые вещи людям, которые видят его впервые, и заставлять их
    догадываться нельзя.

    Правило про русский текст. Английский оставлен как есть: там тире обычный
    знак связи, и запрет сделал бы прозу неестественной.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    def walk(node: object, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, str) and "—" in node:
            if not path.startswith(DASH_AS_LABEL):
                offenders.append(f"{path}: {node[:70]}")

    for name in ("ru.json", "ru/tech.json"):
        walk(json.loads((root / "ui" / "src" / "i18n" / name).read_text(encoding="utf-8")))

    assert not offenders, (
        "тире заменяет связку в текстах для читателя:\n  "
        + "\n  ".join(offenders)
        + "\nПоставьте глагол или предлог."
    )


def test_card_prose_is_translated_field_for_field():
    """Частичный перевод хуже его отсутствия.

    Читатель английской версии, встретив русский абзац посреди страницы, решит,
    что портал сломан, а не что перевод не доделан. Отказ обязан быть виден
    разработчику при сборке, а не читателю на странице.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    ru = json.loads((root / "ui" / "src" / "i18n" / "ru" / "tech.json").read_text(encoding="utf-8"))
    en_path = root / "ui" / "src" / "i18n" / "en" / "tech.json"
    assert en_path.exists(), "английской прозы нет вовсе"
    en = json.loads(en_path.read_text(encoding="utf-8"))

    missing_records = sorted(set(ru) - set(en))
    assert not missing_records, f"записи без английской прозы: {missing_records}"

    missing_fields = sorted(
        f"{key}.{field}" for key in ru for field in ru[key] if field not in en.get(key, {})
    )
    assert not missing_fields, f"поля без перевода: {missing_fields}"

    # Обратное тоже: английский текст без русского оригинала — след опечатки в
    # ключе, и на русской версии он молча пропадёт.
    orphans = sorted(set(en) - set(ru))
    assert not orphans, f"английская проза без русского оригинала: {orphans}"


def test_translated_prose_is_not_a_copy_of_the_original():
    """Скопированный русский текст в английском файле — не перевод.

    Он проходит проверку на полноту и при этом остаётся русским. Отличить одно
    от другого дешевле всего по алфавиту.
    """
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    en = json.loads(
        (root / "ui" / "src" / "i18n" / "en" / "tech.json").read_text(encoding="utf-8")
    )
    cyrillic = re.compile(r"[а-яА-ЯёЁ]{4,}")
    untranslated = sorted(
        f"{key}.{field}" for key, block in en.items() for field, text in block.items()
        if cyrillic.search(text)
    )
    assert not untranslated, f"в английской прозе остался русский текст: {untranslated}"
