"""Оценка пригодности кандидата: порядок просмотра, а не утверждение о работе.

Правило существует ради одного: отделить работу об устройстве извлечения от
применения RAG к предметной области. Все находки помечены каталогом как
относящиеся к RAG, и по одной этой метке отличить архитектуру от применения
нельзя.

Проверки строятся на настоящих находках: восстановление исторических
документов, экономические модели мира и переранжировщик существуют, и правило
обязано ставить их в правильном порядке.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.candidate_fit import MAX_SCORE, assess  # noqa: E402

MECHANISM = (
    "We build an index over passages, embed each chunk with a dense retriever "
    "and rerank the results against the query."
)


def tasks(*slugs: str) -> list[dict]:
    return [{"slug": slug} for slug in slugs]


def codes(fit) -> list[str]:
    return [signal["code"] for signal in fit.signals]


# ─── Признаки ────────────────────────────────────────────────────────────────


def test_task_within_the_subject_weighs_most():
    fit = assess(title="Something", abstract="", tasks=tasks("retrieval"))
    assert fit.score == 4
    assert codes(fit) == ["coreTask"]


def test_named_work_scores_higher_than_an_unnamed_one():
    named = assess(title="LAMAR: A Reranker", abstract="", tasks=tasks("retrieval"))
    plain = assess(title="A study of rerankers", abstract="", tasks=tasks("retrieval"))
    assert named.score > plain.score
    assert "named" in codes(named)
    assert "named" not in codes(plain)


def test_mechanism_vocabulary_lifts_the_score():
    with_words = assess(title="X", abstract=MECHANISM, tasks=tasks("agents"))
    without = assess(title="X", abstract="We study Greek poetry.", tasks=tasks("agents"))
    assert with_words.score > without.score


def test_foreign_field_lowers_the_score_when_the_subject_is_absent():
    """Восстановление исторических документов помечено обработкой изображений."""
    fit = assess(
        title="Leveraging External Knowledge for Historical Document Restoration",
        abstract="We restore damaged manuscripts.",
        tasks=tasks("image-restoration", "document-understanding"),
    )
    assert "offTask" in codes(fit)
    assert fit.score <= 2


def test_foreign_field_does_not_lower_a_work_about_retrieval():
    """Извлечение в мультимодальной системе остаётся извлечением.

    Иначе правило наказывало бы за модальность, а модальность у схемы своё
    измерение и предметом реестра быть не перестаёт.
    """
    fit = assess(
        title="UEmbed: Unified Sparse and Dense Multimodal Embeddings",
        abstract=MECHANISM,
        tasks=tasks("retrieval", "embedding-models", "image-understanding"),
    )
    assert "offTask" not in codes(fit)
    assert fit.score >= 6


# ─── Порядок, ради которого правило существует ───────────────────────────────


def test_architecture_outranks_a_domain_application():
    architecture = assess(
        title="LAMAR: An Open Language-Aware Multilingual Alignment Reranker",
        abstract=MECHANISM,
        tasks=tasks("retrieval"),
    )
    application = assess(
        title="From Economic Agents to Agentic Economies: A Systems Blueprint",
        abstract="We simulate how economies evolve from within.",
        tasks=tasks("agents", "world-models"),
    )
    assert architecture.score > application.score


# ─── Свойства оценки ─────────────────────────────────────────────────────────


def test_score_stays_within_bounds():
    everything = assess(
        title="NAME: A thing",
        abstract=MECHANISM + " sparse bm25 corpus knowledge graph grounding",
        tasks=tasks("retrieval", "agents"),
    )
    assert 0 <= everything.score <= MAX_SCORE

    nothing = assess(title="", abstract="", tasks=tasks("world-models"))
    assert nothing.score == 0, "ниже нуля оценка не опускается"


def test_signals_are_codes_and_not_phrases():
    """Портал двуязычен, и фраза, собранная правилом, была бы на одном языке."""
    fit = assess(title="NAME: A thing", abstract=MECHANISM, tasks=tasks("retrieval"))
    assert fit.signals
    for signal in fit.signals:
        assert set(signal) <= {"code", "tasks", "count"}
        assert signal["code"].isalpha() or signal["code"].isidentifier()


def test_assessment_is_reproducible():
    """Одни и те же данные дают одну и ту же оценку: правило детерминированное."""
    args = dict(title="NAME: A thing", abstract=MECHANISM, tasks=tasks("retrieval"))
    assert assess(**args).as_dict() == assess(**args).as_dict()


@pytest.mark.parametrize("tasks_value", [None, [], [{}], ["строка"], [{"name": "x"}]])
def test_broken_task_list_does_not_raise(tasks_value):
    """Каталог может отдать что угодно, и оценка не должна ронять проход."""
    fit = assess(title="X", abstract="", tasks=tasks_value)
    assert 0 <= fit.score <= MAX_SCORE
