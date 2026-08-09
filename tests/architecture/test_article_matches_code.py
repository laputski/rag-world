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
    stale = re.findall(r"0,9(?!984)\d{1,3}\b", text)
    assert not stale, f"в статье остались прежние значения степени независимости: {stale}"


def test_schema_size_claim_matches_declaration():
    """Число измерений в тексте совпадает с объявленным."""
    text = _article_text()
    assert len(DIMENSIONS) == 26, "изменился состав схемы — обновите статью и этот тест"
    assert "двадцати шести измерений" in text or "26 измерений" in text


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
