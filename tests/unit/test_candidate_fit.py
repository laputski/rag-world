"""How well a candidate fits: an order of review, not a claim about the work.

The rule exists for one purpose: to tell work about the make-up of RAG from work
applying RAG to a subject area. Every find is tagged by the catalogue as relating
to RAG, and that tag alone cannot tell an architecture from an application.

The checks are built on real finds: restoring historical documents, economic world
models, and an existing reranker. The rule has to put them in the right order.
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


# ─── The signals ─────────────────────────────────────────────────────────────


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
    """Restoring historical documents is tagged as document processing."""
    fit = assess(
        title="Leveraging External Knowledge for Historical Document Restoration",
        abstract="We restore damaged manuscripts.",
        tasks=tasks("image-restoration", "document-understanding"),
    )
    assert "offTask" in codes(fit)
    assert fit.score <= 2


def test_foreign_field_does_not_lower_a_work_about_retrieval():
    """Retrieval in a multimodal system is still retrieval.

    Otherwise the rule would penalise modality, and modality is a dimension of the
    schema and does not stop being the registry's subject.
    """
    fit = assess(
        title="UEmbed: Unified Sparse and Dense Multimodal Embeddings",
        abstract=MECHANISM,
        tasks=tasks("retrieval", "embedding-models", "image-understanding"),
    )
    assert "offTask" not in codes(fit)
    assert fit.score >= 6


# ─── The order the rule exists for ───────────────────────────────────────────


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


# ─── Properties of the score ─────────────────────────────────────────────────


def test_score_stays_within_bounds():
    everything = assess(
        title="NAME: A thing",
        abstract=MECHANISM + " sparse bm25 corpus knowledge graph grounding",
        tasks=tasks("retrieval", "agents"),
    )
    assert 0 <= everything.score <= MAX_SCORE

    nothing = assess(title="", abstract="", tasks=tasks("world-models"))
    assert nothing.score == 0, "the score never falls below zero"


def test_signals_are_codes_and_not_phrases():
    """The portal is bilingual, and a phrase built by a rule would be in one language."""
    fit = assess(title="NAME: A thing", abstract=MECHANISM, tasks=tasks("retrieval"))
    assert fit.signals
    for signal in fit.signals:
        assert set(signal) <= {"code", "tasks", "count"}
        assert signal["code"].isalpha() or signal["code"].isidentifier()


def test_assessment_is_reproducible():
    """The same data yields the same score: the rule is deterministic."""
    args = dict(title="NAME: A thing", abstract=MECHANISM, tasks=tasks("retrieval"))
    assert assess(**args).as_dict() == assess(**args).as_dict()


@pytest.mark.parametrize("tasks_value", [None, [], [{}], ["a string"], [{"name": "x"}]])
def test_broken_task_list_does_not_raise(tasks_value):
    """The catalogue may return anything, and the scoring must not crash the pass."""
    fit = assess(title="X", abstract="", tasks=tasks_value)
    assert 0 <= fit.score <= MAX_SCORE
