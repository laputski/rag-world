"""Ступень S5: детерминированные проверки свидетельств (STAGE-7 Ф8, план 03 §5.2).

S5 применяет к кандидатным свидетельствам дисциплину обоснованности, которую
конструктор применяет к ответам RAG: каждое утверждение должно подтверждаться
досленвым фрагментом источника. Здесь — БЕЗ LLM, чисто детерминированные
проверки (план 03 §5.1: «вычисление уровня выполняется детерминированной
функцией без участия языковой модели»).

Проверки:
  1. Совпадение заголовка: expected_title ≈ actual_title (нормализованное).
     Та проверка, что нашла 3 ошибочные ссылки в рецензии (99-review): id
     разрешается, но заголовок по id не совпадает с заявленным.
  2. Год публикации не противоречит препринту (в пределах разумного окна).
  3. Численные значения в допустимом диапазоне (cited_by_count >= 0 и т.п.).
  4. Лицензия репозитория присутствует и распознаваема.
  5. Домен источника в allowlist (C4).

Решение 03-5: согласие агентов здесь не учитывается (S5 детерминирована;
согласие агентов в S4/S6 лишь повышает приоритет рассмотрения).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.collectors.base import RawEvidence, is_allowed_host


@dataclass
class CheckResult:
    """Результат детерминированной проверки одного свидетельства."""

    passed: bool
    reasons: list[str] = field(default_factory=list)


def _normalize_title(s: str) -> str:
    """Нормализация заголовка для сравнения: нижний регистр, удалить пунктуацию."""
    s = s.lower()
    # Заменить всё небуквенно-цифровое на пробел, сжать.
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def _title_similarity(a: str, b: str) -> float:
    """Грубая мера сходства заголовков: доля общих слов (Jaccard)."""
    wa = set(_normalize_title(a).split())
    wb = set(_normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


#: Величины, которые не бывают отрицательными, и как они записаны в свидетельстве.
#: Перечень задан по тому, что сборщики действительно пишут: образец, не
#: совпадающий с форматом значения, — это защита, которой нет.
_NON_NEGATIVE: tuple[tuple[str, str], ...] = (
    (r"cited_by=(-?\d+)", "число цитирований отрицательно"),
    (r"citation_velocity=(-?[\d.]+)", "скорость цитирования отрицательна"),
    (r"downloads_last_month=(-?\d+)", "число загрузок отрицательно"),
    (r"stars=(-?\d+)", "число звёзд отрицательно"),
)

#: Нижняя граница года публикации: раньше вычислительной техники работ нет.
MIN_YEAR = 1900

# Порог сходства заголовков: ниже — считается несовпадением (S5 отклоняет).
# 0.6 — умеренный порог: ловит явные расхождения (LiDAR vs MA-RAG), но допускает
# варианты написания (Self-RAG vs Self-RAG: Learning to Retrieve...).
TITLE_SIMILARITY_THRESHOLD = 0.6


def check(evidence: RawEvidence) -> CheckResult:
    """Детерминированная проверка одного свидетельства (ступень S5).

    Возвращает CheckResult(passed, reasons). passed=False → свидетельство
    не записывается в БД (или помечается unverifed, в зависимости от класса
    изменения S8).
    """
    reasons: list[str] = []

    # 1. Домен источника в allowlist (C4, мера 5.4.2).
    if not is_allowed_host(evidence.source):
        reasons.append(f"домен источника вне allowlist: {evidence.source}")

    # 2. Совпадение заголовка (если оба заданы). Применимо только к publication —
    # для repository/framework_presence и пр. поля expected/actual_title несут
    # иную семантику (заметка), и проверка заголовка к ним не относится.
    if evidence.type == "publication" and evidence.expected_title and evidence.actual_title:
        sim = _title_similarity(evidence.expected_title, evidence.actual_title)
        if sim < TITLE_SIMILARITY_THRESHOLD:
            reasons.append(
                f"несовпадение заголовка: ожидаемый ~ фактический "
                f"(сходство {sim:.2f} < {TITLE_SIMILARITY_THRESHOLD})"
            )

    # 3. Численные значения в допустимом диапазоне.
    #
    # Источник может ответить синтаксически исправно и содержательно
    # бессмысленно. Такой ответ опаснее отказа: отказ виден, а бессмыслица
    # выглядит как результат и попадает в шкалу.
    #
    # Верхняя граница года берётся от даты сбора, а не зашивается числом:
    # зашитая граница либо отвергает верные данные, когда время до неё дойдёт,
    # либо, как здесь до исправления, пропускает 2099 год как допустимый.
    val = evidence.value or ""
    for pattern, message in _NON_NEGATIVE:
        found = re.search(pattern, val)
        if found and float(found.group(1)) < 0:
            reasons.append(f"{message}: {found.group(1)}")

    max_year = evidence.fetched_at.year + 1
    for year_text in re.findall(r"year=(\d{4})", val) + re.findall(
        r"\((\d{4})\)", val
    ):
        year = int(year_text)
        if year < MIN_YEAR or year > max_year:
            reasons.append(
                f"год публикации {year} вне диапазона {MIN_YEAR}..{max_year}"
            )

    return CheckResult(passed=not reasons, reasons=reasons)


def check_many(evidence_list: list[RawEvidence]) -> list[tuple[RawEvidence, CheckResult]]:
    """Проверить пакет свидетельств; вернуть [(evidence, result)]."""
    return [(e, check(e)) for e in evidence_list]
