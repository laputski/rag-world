"""Требования к прозе карточек технологий.

Проза — единственный текст портала, который пишется руками и ничем не
выводится из данных. Поэтому она и портится незаметно: испорченное описание
выглядит как описание, проверки данных до него не достают, а читатель молча
уходит.

Проверяются четыре свойства, каждое из которых уже нарушалось.

**Ссылки вида `[4]`.** Проза пришла из статьи с пронумерованным списком
литературы. Списка на портале нет, номер никуда не ведёт, и читатель видит
обрывок чужой системы отсчёта. Источники у записи свои и стоят ссылками
наверху карточки.

**Транслитерированный жаргон.** «Эмбеддит», «чанки», «промпт», «прунинг» — это
не термины, а английские слова, записанные кириллицей. Термин определяется и
употребляется одинаково; жаргон каждый пишет по-своему, и читатель, не знающий
исходного слова, не восстановит его никак.

**Аббревиатуры без расшифровки.** `LLM` в русском тексте не расшифровано нигде
на портале. «Большая языковая модель» длиннее ровно на четыре слова и не
требует от читателя знать, что стоит за тремя буквами.

**Один абзац на всё описание.** Описание в двести слов, поданное сплошняком,
не читают. Разбивка на абзацы — часть текста, а не оформления.

Отдельно проверяется, что английская проза есть везде, где есть русская:
частичный перевод должен быть виден разработчику, а не читателю.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RU_PATH = ROOT / "ui" / "src" / "i18n" / "ru" / "tech.json"
EN_PATH = ROOT / "ui" / "src" / "i18n" / "en" / "tech.json"

#: Поля прозы, которые читает посетитель карточки.
FIELDS = ("short", "full", "problem", "barriers", "solutions", "maturityNote")

#: Развёрнутые описания, к которым предъявляются требования объёма и разбивки.
LONG_FIELDS = ("full", "problem", "barriers", "solutions")

#: Наименьшая длина развёрнутого описания. Ниже этого «подробное описание»
#: превращается в пересказ краткой сути другими словами.
MIN_FULL = 700

#: Жаргон и замены, которыми он вытесняется.
#:
#: Ключ — образец поиска, а не слово: корень «скор» без уточнения нашёл бы
#: «скорость», а «ретрив» без уточнения не нашёл бы ничего лишнего. Образцы
#: выписаны явно, чтобы проверка ловила жаргон и не спотыкалась об обычные
#: русские слова.
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

#: Аббревиатуры, которые в русском тексте не расшифровываются нигде.
UNEXPANDED = ("LLM", "SOTA", "QA-", "IR-")


def _load(path: Path) -> dict[str, dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


RU = _load(RU_PATH)
EN = _load(EN_PATH)


def _texts(table: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    """Тройки «запись, поле, текст» по всей прозе."""
    return [
        (key, field, value[field])
        for key, value in table.items()
        for field in FIELDS
        if value.get(field)
    ]


def test_no_bibliographic_references():
    """Номер в квадратных скобках указывает на список, которого нет."""
    found = [
        f"{key}.{field}: {match.group(0)}"
        for key, field, text in _texts(RU) + _texts(EN)
        for match in [re.search(r"\[\d+\]", text)]
        if match
    ]
    assert not found, (
        "проза ссылается на пронумерованный список литературы, которого на "
        f"портале нет: {found}. Источники записи стоят ссылками на карточке."
    )


def test_no_transliterated_jargon():
    """Жаргон вытесняется термином, а не остаётся английским словом кириллицей."""
    found: list[str] = []
    for key, field, text in _texts(RU):
        lowered = text.lower()
        for pattern, replacement in JARGON.items():
            match = re.search(rf"\b(?:{pattern})", lowered)
            if match:
                found.append(f"{key}.{field}: «{match.group(0)}» вместо «{replacement}»")
    assert not found, "в русской прозе остался жаргон:\n  " + "\n  ".join(found)


def test_no_unexpanded_abbreviations():
    """Аббревиатура без расшифровки требует от читателя знать её заранее."""
    found = [
        f"{key}.{field}: {abbr}"
        for key, field, text in _texts(RU)
        for abbr in UNEXPANDED
        if abbr in text
    ]
    assert not found, (
        f"в русской прозе аббревиатуры без расшифровки: {found}. "
        "Расшифровка занимает несколько слов и снимает требование к читателю."
    )


def test_no_em_dash_as_connector():
    """Правило проекта: в текстах для читателя тире не заменяет связку.

    Проверка запрещает длинное тире целиком, а не только в роли связки:
    отличить роли разбором нельзя, а глагол или предлог на месте тире читается
    лучше во всех случаях.
    """
    found = [
        f"{key}.{field}"
        for key, field, text in _texts(RU) + _texts(EN)
        if "—" in text
    ]
    assert not found, (
        f"в прозе длинное тире: {found}. Вместо него ставится глагол или предлог."
    )


@pytest.mark.parametrize("language,table", [("ru", RU), ("en", EN)])
def test_full_description_is_detailed_and_broken_into_paragraphs(language, table):
    """Развёрнутое описание пишется абзацами и по существу."""
    short_ones: list[str] = []
    single_block: list[str] = []
    for key, value in table.items():
        text = value.get("full")
        if not text:
            continue
        if len(text) < MIN_FULL:
            short_ones.append(f"{key} ({len(text)} знаков)")
        if len(re.split(r"\n\s*\n", text.strip())) < 2:
            single_block.append(key)
    assert not short_ones, (
        f"{language}: развёрнутое описание короче {MIN_FULL} знаков и потому "
        f"ничего не добавляет к краткой сути: {short_ones}"
    )
    assert not single_block, (
        f"{language}: описание идёт одним блоком без абзацев и не читается: "
        f"{single_block}"
    )


def test_long_fields_have_no_stray_single_newlines():
    """Одиночный перенос строки внутри абзаца не виден в разметке.

    Абзацы разделяются пустой строкой. Одиночный перенос ничего не делает при
    выводе и означает, что автор рассчитывал на перенос, а получил склейку слов
    через пробел.
    """
    found = [
        f"{key}.{field}"
        for key, field, text in _texts(RU) + _texts(EN)
        if field in LONG_FIELDS and re.search(r"[^\n]\n[^\n]", text)
    ]
    assert not found, (
        f"одиночный перенос строки внутри абзаца: {found}. "
        "Абзацы разделяются пустой строкой."
    )


def _registry_records() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "data" / "technologies").glob("*.json"))
    ]


def test_every_record_is_described():
    """Запись реестра без прозы открывается пустой карточкой.

    Такая карточка выглядит поломкой портала, а не отсутствием текста, и
    сообщает читателю ровно ничего. Шесть записей однажды так и стояли.
    """
    undescribed: list[str] = []
    for record in _registry_records():
        prose_id = record.get("prose_id")
        if not prose_id:
            undescribed.append(f"{record['id']}: нет prose_id")
            continue
        prose = RU.get(prose_id)
        if not prose:
            undescribed.append(f"{record['id']}: prose_id={prose_id} без прозы")
            continue
        if not prose.get("short"):
            undescribed.append(f"{record['id']}: нет краткой сути")
        rubric = all(prose.get(field) for field in ("problem", "barriers", "solutions"))
        if not prose.get("full") and not rubric:
            undescribed.append(f"{record['id']}: ни развёрнутого описания, ни рубрики")
    assert not undescribed, (
        "записи реестра без описания открываются пустой карточкой: "
        f"{undescribed}"
    )


def test_english_prose_exists_wherever_russian_does():
    """Частичный перевод виден разработчику, а не читателю."""
    missing = [
        f"{key}.{field}"
        for key, value in RU.items()
        for field in FIELDS
        if value.get(field) and not EN.get(key, {}).get(field)
    ]
    assert not missing, (
        f"есть русская проза без английской: {missing}. "
        "На английской версии читатель увидит пустое место либо русский абзац."
    )
