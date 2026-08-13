"""Выгружаемые данные локализованы: у русского текста есть английский двойник.

Портал двуязычен, а его артефакты были двуязычны наполовину. Часть полей несла
перевод рядом с оригиналом (`why` и `why_en`), часть оставалась только русской,
и различить одно от другого можно было лишь глазами. Для потребителя, читающего
данные без портала, это означало реестр, наполовину написанный на языке,
которого он не знает.

Проверка обходит каждый опубликованный файл и требует: если строка содержит
кириллицу, рядом обязано лежать поле с тем же именем и окончанием `_en`.
Соглашение выбрано потому, что оно уже применялось в обоснованиях разбора и в
словаре остатков; вводить второе значило бы завести два способа сказать одно.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ui" / "public" / "data"

CYRILLIC = re.compile("[а-яА-ЯёЁ]")

#: Файлы, публикуемые для внешнего потребителя.
PUBLISHED = ("registry.json", "map.json", "changes.json", "stats.json",
             "residuals.json", "candidates.json", "digest.json", "index.json")

#: Поля, где кириллица законна без двойника.
#:
#: Имя технологии кириллицей было бы ошибкой данных, а не переводом, поэтому
#: исключений по именам здесь нет. Единственное послабление касается полей, чьё
#: содержимое и есть русский текст по назначению: пояснение к самому словарю
#: остатков хранится на обоих языках отдельными записями словаря, а не парой.
EXEMPT_PATHS: tuple[str, ...] = ()


def _walk(node: object, path: str, out: list[tuple[str, str, object]]) -> None:
    """Собрать тройки «путь, ключ, родитель» для всех строк с кириллицей."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and CYRILLIC.search(value):
                out.append((f"{path}.{key}", key, node))
            else:
                _walk(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, f"{path}[]", out)


@pytest.mark.parametrize("name", PUBLISHED)
def test_russian_text_has_an_english_twin(name):
    path = DATA / name
    if not path.exists():
        pytest.skip(f"{name} не собран")
    found: list[tuple[str, str, object]] = []
    _walk(json.loads(path.read_text(encoding="utf-8")), "", found)

    missing = []
    for where, key, parent in found:
        if where in EXEMPT_PATHS:
            continue
        # Кириллица в поле, которое само объявлено английским, означает не
        # недостачу двойника, а непереведённое поле. Требовать для него ещё
        # одного двойника бессмысленно.
        if key.endswith("_en"):
            missing.append(f"{where} (поле объявлено английским, но написано по-русски)")
            continue
        twin = f"{key}_en"
        value = parent.get(twin) if isinstance(parent, dict) else None
        if not (isinstance(value, str) and value.strip()):
            missing.append(f"{where} (нет {twin})")
    # Одно и то же поле повторяется по всем записям; в отчёте достаточно путей.
    unique = sorted({item.split(" (")[0] for item in missing})
    assert not missing, (
        f"{name}: русский текст без английского двойника в полях {unique}. "
        "Потребитель данных получит реестр наполовину на незнакомом языке."
    )


def test_registry_carries_descriptions_in_both_languages():
    """Описание записи обязано быть в выгрузке, а не только на странице.

    Проза жила в ресурсах интерфейса и в артефакты не попадала вовсе. Реестр,
    выгруженный наружу, состоял из кодов и уровней без единого предложения о
    том, что это за технология.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    without: list[str] = []
    for tech in registry["technologies"]:
        described = tech.get("description") and tech.get("description_en")
        rubric = all(
            tech.get(field) and tech.get(f"{field}_en")
            for field in ("problem", "barriers", "solutions")
        )
        if not (tech.get("summary") and tech.get("summary_en")):
            without.append(f"{tech['id']}: нет краткой сути")
        elif not described and not rubric:
            without.append(f"{tech['id']}: нет развёрнутого описания")
    assert not without, "записи выгружены без описания: " + "; ".join(without)


def test_feed_is_published_in_both_languages():
    """Лента односоставна по устройству, поэтому языков две ленты, а не одна."""
    for name, language in (("feed.xml", "en"), ("feed.ru.xml", "ru")):
        path = DATA / name
        assert path.exists(), f"нет ленты {name}"
        text = path.read_text(encoding="utf-8")
        assert f"<language>{language}</language>" in text, (
            f"{name}: язык ленты не объявлен либо объявлен неверно"
        )
    english = (DATA / "feed.xml").read_text(encoding="utf-8")
    assert not CYRILLIC.search(english), (
        "английская лента содержит русский текст"
    )


def test_index_names_both_feeds():
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    feeds = index.get("feeds")
    assert isinstance(feeds, dict), "указатель не называет ленты по языкам"
    assert set(feeds) == {"en", "ru"}, f"ленты в указателе: {sorted(feeds)}"
