"""The framework-presence collector.

A technology present in a widely used framework is one of the sufficient
conditions for the level at which a technique has left the paper that introduced
it: presence means somebody other than the authors wrote an implementation. That
level is unreachable without this collector, however well known the technique.

Three frameworks are polled by reading the directory listings of their
integration folders. Code search is not used: it requires an account and it
matches comments and tests, which produce false positives where what is wanted
is the fact that an integration exists.

Matching is strict. The name of a file or folder must equal the technology's
name or one of its aliases in full after normalisation. Substring matching would
find "RAG" inside a good hundred names.

The number of requests is small — a few for the whole registry rather than a few
per record — so the poll runs inside the same weekly pass as everything else.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class FrameworkCatalog:
    """A framework and the folders its integrations live in."""

    name: str
    repo: str
    paths: tuple[str, ...]


#: The folders are chosen to hold integrations rather than the framework core.
CATALOGS: tuple[FrameworkCatalog, ...] = (
    # This repository has been rearranged before: the integrations moved out of
    # libs/community into libs/langchain/langchain_classic. The paths were
    # checked by asking for the listing. Should they move again, the collector
    # reports it through the status code rather than falling silent — silence
    # would look exactly like an absence of integrations in reality.
    FrameworkCatalog(
        "LangChain", "langchain-ai/langchain",
        (
            "libs/langchain/langchain_classic/retrievers",
            "libs/langchain/langchain_classic/vectorstores",
            "libs/partners",
        ),
    ),
    FrameworkCatalog(
        "LlamaIndex", "run-llama/llama_index",
        (
            "llama-index-integrations/retrievers",
            "llama-index-integrations/vector_stores",
            "llama-index-integrations/indices",
        ),
    ),
    FrameworkCatalog(
        "Haystack", "deepset-ai/haystack",
        ("haystack/components/retrievers", "haystack/components/rankers"),
    ),
)


def normalize(name: str) -> str:
    """A name without separators or case, so "Light-RAG" and "lightrag" match."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


#: Words that cannot serve as a matching key even when the registry lists them
#: as an alias. They name a notion rather than a technology and match anything:
#: one framework has a `memory` component for conversation history, and the
#: record "RAG as Memory" wrongly received a presence evidence through it. What
#: is matched must be a name, not a common word.
GENERIC_TERMS: frozenset[str] = frozenset({
    "memory", "index", "indices", "graph", "search", "edge", "unified",
    "causal", "embodied", "federated", "streaming", "speculative", "modular",
    "agentic", "retrieval", "retriever", "reranker", "ranking", "vector",
    "store", "stores", "chunking", "generation", "adaptive", "corrective",
    "multimodal", "temporal", "spatial", "hybrid", "dense", "sparse",
})


def _strip_prefixes(stem: str) -> set[str]:
    """The variants of a listing entry's name with framework prefixes removed.

    Integrations are named in several ways: `langchain-qdrant`,
    `llama-index-retrievers-bm25`, or plain `bm25`. All variants take part in
    the comparison.
    """
    parts = re.split(r"[-_]", stem.lower())
    variants = {normalize(stem)}
    drop = {
        "langchain", "llama", "index", "llamaindex", "haystack",
        "retrievers", "retriever", "vector", "stores", "store", "indices",
        "community", "partners", "integrations", "py", "python",
    }
    kept = [p for p in parts if p and p not in drop]
    if kept:
        variants.add(normalize("".join(kept)))
        variants.add(normalize(kept[-1]))
    return {v for v in variants if v}


def fetch_catalog(
    catalog: FrameworkCatalog, *, http: HttpGetter, token: str | None = None
) -> tuple[set[str], list[str]]:
    """The normalised entry names of a framework's folders, and any poll errors."""
    names: set[str] = set()
    errors: list[str] = []
    headers = {"User-Agent": "rag-world/0.2", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for path in catalog.paths:
        url = f"{GITHUB_API}/repos/{catalog.repo}/contents/{path}"
        if not is_allowed_host(url):
            errors.append(f"{catalog.name}: host outside the allowlist")
            continue
        status, body = http.get(url, headers=headers, timeout=20)
        if status != 200:
            errors.append(f"{catalog.name}/{path}: status {status}")
            continue
        try:
            entries = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            errors.append(f"{catalog.name}/{path}: malformed answer")
            continue
        if not isinstance(entries, list):
            errors.append(f"{catalog.name}/{path}: unexpected shape")
            continue
        for item in entries:
            raw = str(item.get("name", ""))
            stem = re.sub(r"\.(py|md|txt)$", "", raw)
            names |= _strip_prefixes(stem)
    return names, errors


def collect_frameworks(
    technologies: list,
    *,
    http: HttpGetter,
    token: str | None = None,
    today: date | None = None,
) -> tuple[list[RawEvidence], list[str]]:
    """Presence evidence for the whole registry at once.

    It takes a list of records rather than one: the listings are read once per
    framework, after which the matching happens in memory.
    """
    today = today or date.today()
    evidence: list[RawEvidence] = []
    errors: list[str] = []

    catalogs: dict[str, set[str]] = {}
    for catalog in CATALOGS:
        names, catalog_errors = fetch_catalog(catalog, http=http, token=token)
        errors.extend(catalog_errors)
        if names:
            catalogs[catalog.name] = names

    for tech in technologies:
        wanted = {normalize(tech.name)} | {normalize(a) for a in tech.aliases}
        wanted |= {normalize(tech.id)}
        # Forms that are too short or too general are dropped: they match a
        # multitude of unrelated names, and false evidence is worse than none.
        wanted = {
            w for w in wanted if len(w) >= 4 and w not in GENERIC_TERMS
        }
        if not wanted:
            continue
        present = [name for name, entries in catalogs.items() if wanted & entries]
        if not present:
            continue
        evidence.append(RawEvidence(
            technology_id=tech.id,
            type="framework_presence",
            value=f"frameworks={', '.join(sorted(present))}",
            source=f"{GITHUB_API}/repos/"
                   + next(c.repo for c in CATALOGS if c.name == present[0]),
            fetched_at=today,
            obtained_by="auto",
            verified=False,
        ))
    return evidence, errors


def result_for(
    technologies: list, *, http: HttpGetter, token: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Wrap the evidence in the common result type."""
    evidence, errors = collect_frameworks(
        technologies, http=http, token=token, today=today
    )
    result = CollectResult(source_name="frameworks", technology_id="*")
    result.evidence.extend(evidence)
    result.errors.extend(errors)
    return result
