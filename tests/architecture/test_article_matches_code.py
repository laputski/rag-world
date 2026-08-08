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
