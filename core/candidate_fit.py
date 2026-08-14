"""How well a candidate fits the registry: a deterministic rule, no model involved.

Discovery brings in around twenty works a week, every one of them tagged in the
catalogue as RAG. The registry, meanwhile, holds **named retrieval
technologies**, while most of what turns up are applications of RAG to some
field: restoring historical documents, answering over chemistry literature,
economic world models. Reading twenty abstracts in a row to tell one from the
other is a habit that dies in the third week.

Hence the score. It is **not a claim about the work** but an order of review: it
says what to look at first. That is exactly why it lives only in the candidate
queue and never reaches a technology card. On a card, everything the portal says
has to be checkable; here it is a heuristic.

The signals are named and shown alongside the score. A number without its terms
would amount to "take our word for it", and the portal is built on the opposite.

What the score deliberately leaves out:

* **citation counts.** For a work a week old the count is zero for everyone, so
  the signal separates nothing;
* **whether a repository exists.** The catalogue does not fill that field: of
  twenty-four works found, zero listed one. A signal that is always zero looks
  like data without being data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Catalogue task tags that fall inside the registry's subject. The list was
#: derived from what the catalogue actually tags RAG work with, not from guesswork.
CORE_TASKS = frozenset({
    "retrieval",
    "embedding-models",
    "learning-to-rank",
})

#: Tags adjacent to the subject: the work may be a retrieval architecture or an
#: application of one. On their own they settle little.
NEAR_TASKS = frozenset({
    "question-answering",
    "reasoning",
    "summarization",
    "agents",
    "language-modeling",
    # Document understanding belongs to the registry's subject and to other
    # fields alike: restoring historical manuscripts carries the same tag. This
    # tag alone does not make a work a work about retrieval.
    "document-understanding",
})

#: Tags that point at another field. The signal counts against a work only when
#: no core tag is present at all: a paper about retrieval inside a multimodal
#: system is still a paper about retrieval.
OFF_TASKS = frozenset({
    "image-restoration",
    "image-understanding",
    "audio-understanding",
    "world-models",
    "reinforcement-learning",
    "instruction-following",
    "coding-agents",
    "speech-recognition",
    "text-to-image",
})

#: Words used to describe how retrieval is built. They are counted in the
#: abstract: a paper about an architecture talks of indexes, chunking and
#: reranking, while an application talks about its field.
MECHANISM_WORDS = (
    "retriev", "index", "chunk", "passage", "rerank", "re-rank", "embedding",
    "vector", "corpus", "knowledge graph", "grounding", "context window",
    "query rewrit", "hybrid search", "sparse", "dense", "bm25", "recall@",
)

#: A title of the form "LEDGERMIND: Provenance-Constrained…": the name comes
#: before the colon and is short. Registry records are named things, and a work
#: naming itself is strong evidence that it proposes one rather than applies
#: someone else's.
_NAMED = re.compile(r"^\s*([A-Z][\w.\-]{1,24}(?:\s[A-Z][\w.\-]{1,24})?)\s*:")

MAX_SCORE = 10


@dataclass
class Fit:
    """A fitness score and the terms it is made of.

    The terms are shown to the reader along with the number: a score without
    them asks for trust, and there is nothing here to trust it on.

    A signal is recorded as a code and its parameters, not as a finished phrase.
    The reason is the one behind the residual vocabulary: the portal is
    bilingual, and a phrase assembled by a rule would reach both readers in one
    language.
    """

    score: int = 0
    signals: list[dict] = field(default_factory=list)

    def add(self, score: int, code: str, **params: object) -> None:
        self.score += score
        self.signals.append({"code": code, **params})

    def as_dict(self) -> dict:
        return {"score": self.score, "signals": list(self.signals)}


def _task_slugs(tasks: list[dict] | None) -> set[str]:
    return {
        t.get("slug", "") for t in (tasks or []) if isinstance(t, dict)
    } - {""}


def assess(
    *,
    title: str,
    abstract: str,
    tasks: list[dict] | None = None,
    curated_by: list[str] | None = None,
) -> Fit:
    """Score how well a work fits the registry, from its catalogue entry.

    Returns a whole number from zero to ten and the signals that fired. Whole,
    not fractional: precision here would be imaginary, and ten steps are enough
    to sort a couple of dozen works.
    """
    fit = Fit()
    slugs = _task_slugs(tasks)

    # Inclusion in a topic list is a decision by someone who works in the field,
    # whereas a catalogue task tag was applied by whoever uploaded the work.
    # Without this signal, works found through lists would score low not for
    # their properties but for the poverty of the source: a list carries no
    # task tags at all.
    if curated_by:
        fit.add(2, "curatedList", lists=sorted(curated_by))

    core = sorted(slugs & CORE_TASKS)
    if core:
        fit.add(4, "coreTask", tasks=core)

    near = sorted(slugs & NEAR_TASKS)
    if near:
        fit.add(2, "nearTask", tasks=near)

    if _NAMED.match(title or ""):
        fit.add(2, "named")

    text = (abstract or "").lower()
    hits = sorted({word for word in MECHANISM_WORDS if word in text})
    if len(hits) >= 6:
        fit.add(2, "mechanismStrong", count=len(hits))
    elif len(hits) >= 3:
        fit.add(1, "mechanismWeak", count=len(hits))

    off = sorted(slugs & OFF_TASKS)
    if off and not core:
        fit.add(-3, "offTask", tasks=off)

    fit.score = max(0, min(MAX_SCORE, fit.score))
    return fit
