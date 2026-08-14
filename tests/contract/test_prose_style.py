"""What the prose of the technology cards has to satisfy.

The prose is the only text of the portal written by hand rather than derived from
data. That is why it decays unnoticed: spoiled prose still looks like a
description, the data checks do not reach it, and a reader takes what is given.

Four properties are checked, and each of them has been broken here before.

**References of the form `[4]`.** The prose came from an article with a numbered
bibliography. There is no such list on the portal, the number leads nowhere, and
the reader meets a fragment of somebody else's frame of reference. A record has
sources of its own, and they stand at the top of the card.

**Transliterated jargon.** Words like "эмбеддит" and "чанки" are not terms but
English words written in Cyrillic. A term is used the same way by everyone;
jargon is spelled differently by everyone, and a reader who does not know the
original word cannot recover it.

**Abbreviations without expansion.** `LLM` is not expanded anywhere on the
portal. The expansion is a few words longer and asks nothing of the reader.

**One paragraph for a whole description.** A two-hundred-word description served
as a single block goes unread. Splitting it into paragraphs is part of the text
rather than of its presentation.

Separately it is checked that English prose exists wherever Russian prose does: a
partial translation should be visible to the developer and not to the reader.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RU_PATH = ROOT / "ui" / "src" / "i18n" / "ru" / "tech.json"
EN_PATH = ROOT / "ui" / "src" / "i18n" / "en" / "tech.json"

#: The prose fields a visitor to a card actually reads.
FIELDS = ("short", "full", "problem", "barriers", "solutions", "maturityNote")

#: The full descriptions the requirements of length and paragraphing apply to.
LONG_FIELDS = ("full", "problem", "barriers", "solutions")

#: The least length of a full description. Below it the "detail" turns into the
#: short summary retold in other words.
MIN_FULL = 700

#: The jargon and what displaces it.
#:
#: The key is a search pattern rather than a word: some Russian roots overlap
#: with ordinary words, so the patterns are written out explicitly for the check
#: to catch jargon without tripping over legitimate Russian.
JARGON = {
    r"эмбед\w*": "векторное представление",
    r"эмбеддинг\w*": "векторное представление",
    r"чанк\w*": "фрагмент",
    r"промпт\w*": "подсказка либо вход модели",
    r"прунинг\w*": "отсечение",
    r"пайплайн\w*": "цепочка обработки",
    r"ретрив\w*": "извлекатель либо извлечение",
    r"скоринг\w*": "оценивание",
    r"инференс\w*": "вывод модели",
    r"бенчмарк\w*": "эталонный набор задач",
    r"датасет\w*": "набор данных",
    r"фича\w*|фичи\b": "признак",
    r"тюнинг\w*|файнтюнинг\w*": "донастройка",
    r"энкодер\w*": "кодировщик",
    r"декодер\w*": "декодировщик",
    r"оверхед\w*": "накладные расходы",
    r"перформанс\w*": "производительность",
    r"юзкейс\w*": "сценарий применения",
    r"квери\w*": "запрос",
    r"тул\b|тулз\b": "инструмент",
}

#: Abbreviations that go unexpanded in the Russian text.
UNEXPANDED = ("LLM", "SOTA", "QA-", "IR-")


def _load(path: Path) -> dict[str, dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


RU = _load(RU_PATH)
EN = _load(EN_PATH)


def _texts(table: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    """Triples of record, field and text across the whole prose."""
    return [
        (key, field, value[field])
        for key, value in table.items()
        for field in FIELDS
        if value.get(field)
    ]


def test_no_bibliographic_references():
    """A number in square brackets points at a list that does not exist here."""
    found = [
        f"{key}.{field}: {match.group(0)}"
        for key, field, text in _texts(RU) + _texts(EN)
        for match in [re.search(r"\[\d+\]", text)]
        if match
    ]
    assert not found, (
        "the prose refers to a numbered bibliography that the portal does not "
        f"have: {found}. The sources of a record stand as links at the top of the "
        "card."
    )


def test_no_transliterated_jargon():
    """Jargon is displaced by a term rather than left as an English word."""
    found: list[str] = []
    for key, field, text in _texts(RU):
        lowered = text.lower()
        for pattern, replacement in JARGON.items():
            match = re.search(rf"\b(?:{pattern})", lowered)
            if match:
                found.append(f"{key}.{field}: «{match.group(0)}» instead of «{replacement}»")
    assert not found, "jargon remains in the Russian prose:\n  " + "\n  ".join(found)


def test_no_unexpanded_abbreviations():
    """An unexpanded abbreviation demands that the reader already know it."""
    found = [
        f"{key}.{field}: {abbr}"
        for key, field, text in _texts(RU)
        for abbr in UNEXPANDED
        if abbr in text
    ]
    assert not found, (
        f"unexpanded abbreviations in the Russian prose: {found}. The expansion "
        "takes a few words and asks nothing of the reader."
    )


def test_no_em_dash_as_connector():
    """A rule of the project: a dash does not stand in for a verb.

    The check forbids the em dash outright rather than only in that role: telling
    the roles apart by parsing is not possible, and a verb or a preposition in its
    place is better in every case.
    """
    found = [
        f"{key}.{field}"
        for key, field, text in _texts(RU) + _texts(EN)
        if "—" in text
    ]
    assert not found, (
        f"an em dash in the prose: {found}. Put a verb or a preposition instead."
    )


@pytest.mark.parametrize("language,table", [("ru", RU), ("en", EN)])
def test_full_description_is_detailed_and_broken_into_paragraphs(language, table):
    """A full description is written in paragraphs and says something."""
    short_ones: list[str] = []
    single_block: list[str] = []
    for key, value in table.items():
        text = value.get("full")
        if not text:
            continue
        if len(text) < MIN_FULL:
            short_ones.append(f"{key} ({len(text)} characters)")
        if len(re.split(r"\n\s*\n", text.strip())) < 2:
            single_block.append(key)
    assert not short_ones, (
        f"{language}: a full description shorter than {MIN_FULL} characters adds "
        f"nothing to the short summary: {short_ones}"
    )
    assert not single_block, (
        f"{language}: the description is one block with no paragraphs and goes "
        f"unread: {single_block}"
    )


def test_long_fields_have_no_stray_single_newlines():
    """A single line break inside a paragraph is invisible in the markup.

    Paragraphs are separated by a blank line. A single break shows up nowhere in
    the output and means the author expected a break while the reader gets a
    space.
    """
    found = [
        f"{key}.{field}"
        for key, field, text in _texts(RU) + _texts(EN)
        if field in LONG_FIELDS and re.search(r"[^\n]\n[^\n]", text)
    ]
    assert not found, (
        f"a single line break inside a paragraph: {found}. "
        "Paragraphs are separated by a blank line."
    )


def _registry_records() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "data" / "technologies").glob("*.json"))
    ]


def test_every_record_is_described():
    """A registry record without prose opens as an empty card.

    Such a card looks like a broken portal rather than like missing data, and it
    tells the reader precisely nothing. Six records were once exactly that.
    """
    undescribed: list[str] = []
    for record in _registry_records():
        prose_id = record.get("prose_id")
        if not prose_id:
            undescribed.append(f"{record['id']}: no prose_id")
            continue
        prose = RU.get(prose_id)
        if not prose:
            undescribed.append(f"{record['id']}: prose_id={prose_id} with no prose")
            continue
        if not prose.get("short"):
            undescribed.append(f"{record['id']}: no short summary")
        rubric = all(prose.get(field) for field in ("problem", "barriers", "solutions"))
        if not prose.get("full") and not rubric:
            undescribed.append(
                f"{record['id']}: neither a full description nor the rubric"
            )
    assert not undescribed, (
        "registry records with no description open as an empty card: "
        f"{undescribed}"
    )


def test_english_prose_exists_wherever_russian_does():
    """A partial translation is visible to the developer, not to the reader."""
    missing = [
        f"{key}.{field}"
        for key, value in RU.items()
        for field in FIELDS
        if value.get(field) and not EN.get(key, {}).get(field)
    ]
    assert not missing, (
        f"Russian prose exists without English: {missing}. In the English version "
        "the reader would meet a blank space or a Russian paragraph."
    )
