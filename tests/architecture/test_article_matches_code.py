"""Числа в научном тексте не должны расходиться с реализацией.

Исходный дефект проекта состоял в том, что код, данные и тексты утверждали
разное об одном и том же. Статья особенно уязвима: её числа набираются руками и
устаревают молча. Один такой случай уже был — текст сообщал степень
независимости «около 0,97», тогда как реализация давала 0,9984.

Тест сверяет утверждения статьи с тем, что выдаёт код. Он намеренно проверяет
немногое: только величины, которые вычисляются, и только там, где расхождение
вводит читателя в заблуждение.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.dimensions_schema import (  # noqa: E402
    DIMENSIONS,
    STRATA,
    dead_values,
    independence_degree,
)

ARTICLE = ROOT / "ui" / "src" / "generalizedData.ts"


def _article_text() -> str:
    assert ARTICLE.exists(), f"текст статьи не найден: {ARTICLE}"
    return ARTICLE.read_text(encoding="utf-8")


def test_independence_degree_matches_implementation():
    """Приведённая в тексте степень независимости совпадает с вычисляемой."""
    text = _article_text()
    computed = independence_degree()
    # В тексте величина записана с запятой в десятичном разделителе.
    expected = f"{computed:.4f}".replace(".", ",")
    assert expected in text, (
        f"в статье нет актуальной степени независимости {expected}; "
        "пересчитайте и обновите текст"
    )
    # Прежние значения ищутся относительно вычисленного, а не по зашитому
    # исключению: зашитое устаревает вместе с числом, и сторож начинает
    # считать устаревшим как раз верное значение. Один такой случай уже был.
    stale = [
        found for found in re.findall(r"0,9\d{3}\b", text) if found != expected
    ]
    assert not stale, f"в статье остались прежние значения степени независимости: {stale}"


# Числительные до тридцати, встречающиеся в тексте прописью. Число измерений
# меняется редко и осознанно, поэтому перечень короткий: важно, чтобы сторож
# требовал обновить статью, а не сам подстраивался под неё.
SPELLED = {
    26: ("двадцати шести", "двадцать шесть", "26"),
    27: ("двадцати семи", "двадцать семь", "27"),
    28: ("двадцати восьми", "двадцать восемь", "28"),
    29: ("двадцати девяти", "двадцать девять", "29"),
    30: ("тридцати", "тридцать", "30"),
}


def _mentions_size_ru(text: str, form: str) -> bool:
    """Число рядом со словом «измерение», в любом из двух порядков."""
    escaped = re.escape(form)
    return bool(
        re.search(rf"{escaped}\s+измерен\w*|измерен\w*\s+{escaped}", text)
    )


def test_schema_size_claim_matches_declaration():
    """Число измерений в тексте совпадает с объявленным.

    Число не зашито: сторож берёт его из схемы. Зашитое устаревает вместе с
    правкой схемы, и тогда падает верный текст — так уже было со степенью
    независимости.

    Проверяется не только присутствие верного числа, но и отсутствие прежних.
    Сторож, доволен первым верным упоминанием, пропускал устаревшие: аннотация
    говорила о двадцати восьми измерениях, а состав схемы двумя разделами ниже
    по-прежнему о двадцати шести.
    """
    text = _article_text()
    size = len(DIMENSIONS)
    assert size in SPELLED, (
        f"в схеме {size} измерений; добавьте написание в SPELLED"
    )
    assert any(_mentions_size_ru(text, form) for form in SPELLED[size]), (
        f"в статье нет актуального числа измерений ({SPELLED[size][0]})"
    )
    stale = [
        form for value, forms in SPELLED.items() if value != size
        for form in forms if _mentions_size_ru(text, form)
    ]
    assert not stale, f"в статье осталось прежнее число измерений: {stale}"


#: Написание числа измерений по-английски. Аннотация переведена, и перевод её
#: чисел устаревает отдельно от оригинала: пока сторож смотрел только в русский
#: текст, английский полгода утверждал двадцать шесть измерений при двадцати
#: восьми объявленных.
SPELLED_EN = {
    26: "twenty-six", 27: "twenty-seven", 28: "twenty-eight",
    29: "twenty-nine", 30: "thirty",
}


def test_english_abstract_states_the_same_schema_size():
    text = _article_text()
    size = len(DIMENSIONS)
    assert size in SPELLED_EN, (
        f"в схеме {size} измерений; добавьте написание в SPELLED_EN"
    )
    assert f"{SPELLED_EN[size]} dimensions" in text, (
        f"в английской аннотации нет актуального числа измерений "
        f"({SPELLED_EN[size]})"
    )
    stale = [
        form for value, form in SPELLED_EN.items()
        if value != size and f"{form} dimensions" in text
    ]
    assert not stale, f"в английской аннотации осталось прежнее число: {stale}"


def test_locale_strings_state_the_current_schema_size():
    """Число измерений называется и в подписях интерфейса, не только в статье.

    Подпись к разделу «Основания» на обоих языках объясняла читателю, «почему
    измерений двадцать шесть», когда их было двадцать восемь. Сторож статьи
    туда не смотрел, потому что это не статья, а строка перевода.
    """
    size = len(DIMENSIONS)
    locales = ROOT / "ui" / "src" / "i18n"

    ru = (locales / "ru.json").read_text(encoding="utf-8")
    stale_ru = [
        form for value, forms in SPELLED.items() if value != size
        for form in forms if _mentions_size_ru(ru, form)
    ]
    assert not stale_ru, f"ru.json называет прежнее число измерений: {stale_ru}"

    en = (locales / "en.json").read_text(encoding="utf-8")
    stale_en = [
        form for value, form in SPELLED_EN.items()
        if value != size and re.search(rf"{form}\s+dimensions?", en)
    ]
    assert not stale_en, f"en.json называет прежнее число измерений: {stale_en}"


def test_strata_count_claim_matches_declaration():
    text = _article_text()
    assert len(STRATA) == 7
    assert "семи стратам" in text or "семь стратов" in text or "семи стратов" in text


def test_dead_values_claim_matches_implementation():
    """Утверждение об отсутствии мёртвых значений проверяется вычислением."""
    text = _article_text()
    claims_none = "Мёртвые значения отсутствуют" in text
    if claims_none:
        assert dead_values() == [], (
            "статья утверждает отсутствие мёртвых значений, "
            f"а вычисление даёт {dead_values()}"
        )


# ─── Ссылки и заявка на новизну ──────────────────────────────────────────────


def test_every_cited_number_has_a_reference():
    """Ссылка на номер, которого нет в списке, уводит читателя в никуда.

    Отказ тихий: в тексте остаётся «[42]», список кончается на сороковом, и
    заметить это можно только вычитыванием. Сверка дешёвая, поэтому делается
    машиной.
    """
    text = _article_text()
    declared = {int(n) for n in re.findall(r'label:\s*"\[(\d+)\]', text)}

    # Сам список источников исключается построчно, а не отсечением по слову
    # «refs»: оно встречается ещё и в объявлении типа, и отсечение по нему
    # оставляло от текста шестьсот символов без единой ссылки. Проверка при
    # этом проходила — она сверяла пустое множество с полным.
    body = "\n".join(
        line for line in text.splitlines()
        if not re.match(r'\s*\{\s*label:\s*"\[\d+\]', line)
    )

    # Групповая ссылка «[2, 3]» разбирается целиком: образец, берущий только
    # первый номер, пропустил бы висящий второй.
    cited: set[int] = set()
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", body):
        cited |= {int(n) for n in re.findall(r"\d+", group)}

    assert cited, "в тексте не найдено ни одной ссылки — образец разбора сломан"
    orphans = sorted(cited - declared)
    assert not orphans, f"цитируются номера без записи в списке: {orphans}"


def test_novelty_claim_stays_narrow():
    """Заявка ограничена проверенным и не возвращается к абсолютной форме.

    Прежняя формулировка утверждала, что применение модели признаков к RAG «не
    опубликовано». Проверка нашла смежные работы, и заявка была сужена до того,
    что действительно проверялось. Сторож не даёт откатиться незаметно.
    """
    text = _article_text()
    assert "конфигурационному пространству не опубликовано" not in text, (
        "вернулась абсолютная заявка на новизну"
    )
    assert "не удалось обнаружить формальной модели признаков" in text, (
        "заявка на новизну сформулирована не как результат поиска"
    )


def test_prior_art_search_states_its_limits():
    """Заявка об отсутствии стоит ровно столько, сколько названные границы."""
    text = _article_text()
    for expected in ("Границы проверки", "Систематического обхода"):
        assert expected in text, f"в разделе о поиске нет упоминания: {expected}"


def test_adjacent_variability_works_are_cited():
    """Смежные работы по управлению изменчивостью названы поимённо.

    Они существуют, применяют тот же аппарат к соседним объектам, и умолчать о
    них значило бы завысить вклад.
    """
    text = _article_text()
    for marker in ("3646548.3672581", "2501.00532", "2602.17697"):
        assert marker in text, f"смежная работа не процитирована: {marker}"


# ─── Размер реестра ──────────────────────────────────────────────────────────
#
# Реестр растёт, и всякое число, посчитанное по нему руками, устаревает молча.
# Так и вышло: заключение полгода утверждало пятьдесят четыре записи, тогда как
# аннотация в той же статье говорила о шестидесяти двух. Читатель видел, как
# портал спорит сам с собой.

#: Обороты, которыми в статье называется размер реестра.
REGISTRY_SIZE_PATTERNS = (
    r"(\S+)\s+(?:запис\w+|технологи\w+|архитектур\w*)\s+(?:из\s+)?реестра",
    r"(\S+)\s+registry\s+(?:technolog\w*|entr\w*)",
)

#: Числительные прописью. Перечень закрытый и служит одному: заметить, что
#: размер реестра написан словами, и потребовать цифр. Значения из него не
#: вычисляются, поэтому сам он не устаревает вместе с реестром, в отличие от
#: списка написаний конкретного числа.
NUMERAL_RU = {
    "одной", "одна", "двух", "две", "трёх", "три", "четырёх", "четыре",
    "пяти", "пять", "шести", "шесть", "семи", "семь", "восьми", "восемь",
    "девяти", "девять", "десяти", "десять", "двадцати", "двадцать",
    "тридцати", "тридцать", "сорока", "сорок", "пятидесяти", "пятьдесят",
    "шестидесяти", "шестьдесят", "семидесяти", "семьдесят", "восьмидесяти",
    "восемьдесят", "девяноста", "девяносто", "ста", "сто",
}
NUMERAL_EN = re.compile(
    r"^(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"(?:twen|thir|for|fif|six|seven|eigh|nine)ty(?:-\w+)?|hundred)$",
    re.IGNORECASE,
)


def _registry_size_claims(text: str) -> list[tuple[str, str]]:
    """Пары «числительное, весь оборот» для каждого утверждения о размере."""
    claims = []
    for pattern in REGISTRY_SIZE_PATTERNS:
        for found in re.finditer(pattern, text):
            claims.append((found.group(1).strip('"«»,;:'), found.group(0)))
    return claims


def test_registry_size_is_written_in_digits():
    """Размер реестра пишется цифрами, иначе его нечем сверить.

    Прописью число не сверить с данными, а меняется оно при каждом пополнении:
    правило «раз в год и осознанно», по которому допущен перечень написаний для
    числа измерений, здесь не работает.
    """
    spelled = [
        whole for word, whole in _registry_size_claims(_article_text())
        if word.lower() in NUMERAL_RU or NUMERAL_EN.match(word)
    ]
    assert not spelled, (
        f"размер реестра написан прописью: {spelled}. Он меняется при каждом "
        "пополнении, и прописью его не сверить с данными. Пишите цифрами."
    )


def test_registry_size_claims_match_the_data():
    """Каждое число записей реестра в тексте совпадает с реестром."""
    from services.registry import store

    total = len(store.load_technologies())
    stated = [
        int(word) for word, _ in _registry_size_claims(_article_text())
        if word.isdigit()
    ]
    assert stated, "в статье не сказано, на скольких записях проверена схема"
    wrong = sorted(set(stated) - {total})
    assert not wrong, (
        f"в статье указан размер реестра {wrong}, а в данных {total} записей"
    )


def test_residual_share_claim_matches_the_registry():
    """«N записей из M» с остатком проверяется по реестру."""
    from services.registry import store

    technologies = store.load_technologies()
    expected = (len([t for t in technologies if t.residual]), len(technologies))
    stated = [
        (int(part), int(whole))
        for part, whole in re.findall(r"(\d+)\s+записей из (\d+)", _article_text())
    ]
    assert stated, "в статье не сказано, у скольких записей остаток непуст"
    wrong = sorted(set(stated) - {expected})
    assert not wrong, (
        f"в статье указано {wrong}, а в реестре {expected[0]} записей "
        f"с непустым остатком из {expected[1]}"
    )


def test_justification_count_matches_the_data():
    """Число обоснований разбора берётся из журнала, а не из памяти."""
    notes = ROOT / "data" / "parse_notes.jsonl"
    expected = len(
        [line for line in notes.read_text(encoding="utf-8").splitlines() if line.strip()]
    )
    stated = [int(n) for n in re.findall(r"обоснований (\d+)", _article_text())]
    assert stated, "в статье не сказано, сколько обоснований разбора записано"
    wrong = sorted(set(stated) - {expected})
    assert not wrong, (
        f"в статье указано обоснований {wrong}, а в журнале разбора {expected}"
    )


def test_coverage_claim_matches_the_registry():
    """Число покрытия в статье вычисляется, а не пишется от руки.

    Прежде статья утверждала «96 процентов», выведенные из остатков, которых не
    существовало. Теперь остатки заполнены, и число стало проверяемым — значит,
    обязано проверяться.
    """
    from services.registry import store

    text = _article_text()
    technologies = store.load_technologies()
    expressed = [tech for tech in technologies if not tech.residual]
    share = round(100 * len(expressed) / len(technologies))

    # Русский счёт: «74 процента», но «69 процентов». Сторож принимает обе
    # формы — иначе он падал бы на верном числе из-за грамматики.
    tail = share % 10
    forms = [f"{share} процентов"]
    if tail == 1 and share % 100 != 11:
        forms.append(f"{share} процент")
    elif tail in (2, 3, 4) and share % 100 not in (12, 13, 14):
        forms.append(f"{share} процента")

    assert any(form in text for form in forms), (
        f"в статье нет актуальной доли покрытия ({forms[-1]}); "
        "она вычисляется из остатков реестра"
    )
    assert f"{share} percent" in text, (
        f"в английской аннотации нет актуальной доли покрытия ({share} percent)"
    )
