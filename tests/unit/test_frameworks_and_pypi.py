"""Tests of the framework-presence and package-download collectors.

Both open the level L4, unreachable otherwise. Both are also the easiest to give
false evidence, and both did so during development:

* the record "RAG as Memory" received framework presence, because it had the alias
  "memory" and the framework has a component of that name for conversation
  history;
* a package named "raptor" exists and has nothing to do with the recursive tree
  architecture.

False evidence is worse than none: it raises a level and looks like a fact. These
tests pin the protections added after those cases.
"""

from __future__ import annotations

import json
from datetime import date

from services.collectors.frameworks import (
    GENERIC_TERMS,
    _strip_prefixes,
    collect_frameworks,
    normalize,
)
from services.collectors.pypi import MIN_MONTHLY_DOWNLOADS, collect_pypi
from services.registry.store import Technology

TODAY = date(2026, 8, 8)


class FakeHttp:
    """Returns prepared answers by a substring of the address."""

    def __init__(self, routes: dict[str, object], status: int = 200):
        self.routes = routes
        self.status = status
        self.calls: list[str] = []

    def get(self, url: str, headers=None, timeout: int = 20) -> tuple[int, bytes]:
        self.calls.append(url)
        for marker, payload in self.routes.items():
            if marker in url:
                if isinstance(payload, int):
                    return (payload, b"")
                return (self.status, json.dumps(payload).encode())
        return (404, b"[]")


def tech(tech_id: str, name: str, aliases: list[str] | None = None, **kw) -> Technology:
    return Technology(
        id=tech_id, name=name, aliases=aliases or [], kind="technique", **kw
    )


def listing(*names: str) -> list[dict]:
    return [{"name": n} for n in names]


# ─── Parsing the folder names ────────────────────────────────────────────────


def test_prefixes_are_stripped_from_integration_names():
    """Integrations are named in several ways; all variants take part."""
    variants = _strip_prefixes("llama-index-retrievers-bm25")
    assert "bm25" in variants


def test_partner_package_name_is_recognized():
    assert "qdrant" in _strip_prefixes("langchain-qdrant")


def test_file_stem_is_used_as_is():
    assert normalize("multi_query") in _strip_prefixes("multi_query")


# ─── False matches ───────────────────────────────────────────────────────────


def test_generic_alias_does_not_produce_evidence():
    """The main case: a common word matches anything."""
    assert "memory" in GENERIC_TERMS
    http = FakeHttp({"contents": listing("memory.py", "in_memory.py")})
    evidence, _ = collect_frameworks(
        [tech("rag_as_memory", "RAG as Memory", ["memory"])],
        http=http, today=TODAY,
    )
    assert evidence == [], "a common word cannot serve as a matching key"


def test_short_name_does_not_produce_evidence():
    """Three-letter names match a multitude of unrelated ones."""
    http = FakeHttp({"contents": listing("tog.py")})
    evidence, _ = collect_frameworks([tech("tog", "ToG")], http=http, today=TODAY)
    assert evidence == []


def test_substring_match_is_not_enough():
    """Substring matching would find "RAG" inside a good hundred names."""
    http = FakeHttp({"contents": listing("graphrag_retriever.py")})
    evidence, _ = collect_frameworks([tech("rag", "RAG")], http=http, today=TODAY)
    assert evidence == []


def test_exact_name_produces_evidence():
    http = FakeHttp({"contents": listing("qdrant.py", "chroma.py")})
    evidence, _ = collect_frameworks(
        [tech("qdrant", "Qdrant")], http=http, today=TODAY
    )
    assert len(evidence) == 1
    assert evidence[0].type == "framework_presence"
    assert "frameworks=" in (evidence[0].value or "")


def test_alias_produces_evidence():
    http = FakeHttp({"contents": listing("bm25.py")})
    evidence, _ = collect_frameworks(
        [tech("bm25_sparse", "BM25 Sparse", ["BM25"])], http=http, today=TODAY
    )
    assert len(evidence) == 1


def test_unavailable_catalog_is_reported_not_silently_empty():
    """A folder that has moved must say so rather than look empty."""
    http = FakeHttp({"contents": 404})
    evidence, errors = collect_frameworks(
        [tech("qdrant", "Qdrant")], http=http, today=TODAY
    )
    assert evidence == []
    assert errors, "a refusal from the listing has to reach the errors"


def test_malformed_listing_does_not_crash():
    http = FakeHttp({"contents": {"unexpected": "shape"}})
    evidence, errors = collect_frameworks(
        [tech("qdrant", "Qdrant")], http=http, today=TODAY
    )
    assert evidence == []
    assert errors


# ─── Package downloads ───────────────────────────────────────────────────────


def test_downloads_above_threshold_produce_evidence():
    http = FakeHttp({
        "pypi.org/pypi": {"info": {"version": "1.0.0"}},
        "pypistats.org": {"data": {"last_month": 500000}},
    })
    result = collect_pypi("qdrant", "qdrant-client", http=http, today=TODAY)
    assert len(result.evidence) == 1
    assert "downloads_last_month=500000" in (result.evidence[0].value or "")


def test_downloads_below_threshold_produce_nothing():
    """That many come from the authors' own continuous integration."""
    http = FakeHttp({
        "pypi.org/pypi": {"info": {"version": "1.0.0"}},
        "pypistats.org": {"data": {"last_month": MIN_MONTHLY_DOWNLOADS - 1}},
    })
    result = collect_pypi("raptor", "raptor", http=http, today=TODAY)
    assert result.evidence == []
    assert result.skipped


def test_missing_package_produces_nothing():
    http = FakeHttp({}, status=404)
    result = collect_pypi("demo", "nonexistent", http=http, today=TODAY)
    assert result.evidence == []
    assert result.errors


def test_existing_package_without_statistics_produces_nothing():
    """That a package exists is a different claim from how often it is taken."""
    http = FakeHttp({"pypi.org/pypi": {"info": {"version": "1.0.0"}}})
    result = collect_pypi("demo", "demo", http=http, today=TODAY)
    assert result.evidence == [], "the evidence type is called downloads"
    assert result.errors


def test_statistics_name_is_normalized():
    """The statistics service knows "flagembedding" and not "FlagEmbedding"."""
    http = FakeHttp({
        "pypi.org/pypi": {"info": {"version": "1.0"}},
        "pypistats.org": {"data": {"last_month": 600000}},
    })
    collect_pypi("bge_m3", "FlagEmbedding", http=http, today=TODAY)
    stats_call = next(c for c in http.calls if "pypistats.org" in c)
    assert "flagembedding" in stats_call
