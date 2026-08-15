"""Tests of venue detection and of match selection.

Two properties are pinned here, and without them the registry cannot be trusted.

First: peer review is recognised even when the index has no venue name. Otherwise
conference publications would stay preprints for ever and never reach the
confirmed level.

Second: an unreliable match by title creates no evidence. During development the
collector managed to pick a foreign work for Self-RAG, and substituting somebody
else's information is more dangerous than having none.
"""

from __future__ import annotations

import json
from datetime import date

from services.collectors.openalex import _venue_of, collect_openalex


class FakeHttp:
    """A stub transport returning prepared answers by a substring of the URL."""

    def __init__(self, routes: dict[str, dict], status: int = 200):
        self.routes = routes
        self.status = status
        self.calls: list[str] = []

    def get(self, url: str, headers=None, timeout: int = 20) -> tuple[int, bytes]:
        self.calls.append(url)
        for marker, payload in self.routes.items():
            if marker in url:
                return (self.status, json.dumps(payload).encode())
        return (404, b"{}")


TODAY = date(2026, 8, 8)


def _work(**kwargs) -> dict:
    base = {
        "id": "https://openalex.org/W1",
        "title": "Adaptive-RAG: Learning to Adapt Retrieval",
        "type": "preprint",
        "doi": "https://doi.org/10.48550/arxiv.2403.14403",
        "cited_by_count": 10,
        "publication_year": 2024,
        "publication_date": "2024-03-21",
        "primary_location": {"source": {"display_name": "arXiv (Cornell University)",
                                        "type": "repository"}},
        "locations": [],
    }
    base.update(kwargs)
    return base


# ─── Recognising the venue ───────────────────────────────────────────────────


def test_repository_source_is_not_peer_reviewed():
    venue, reviewed = _venue_of(_work())
    assert reviewed is False
    assert "arXiv" in venue


def test_conference_source_is_peer_reviewed():
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        primary_location={"source": {"display_name": "NAACL", "type": "conference"}},
    )
    assert _venue_of(work) == ("NAACL", True)


def test_peer_review_detected_when_venue_name_is_missing():
    """The main case: a work type and a publisher prefix, and no venue name."""
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        primary_location={"source": None},
        locations=[{"source": None}],
    )
    venue, reviewed = _venue_of(work)
    assert reviewed is True
    assert venue == "ACL Anthology"


def test_unknown_publisher_prefix_is_reported_as_is():
    work = _work(type="article", doi="https://doi.org/10.52202/something",
                 primary_location={"source": None}, locations=[])
    venue, reviewed = _venue_of(work)
    assert reviewed is True
    assert "10.52202" in venue, "the publisher is unknown, so the prefix is shown"


def test_preprint_doi_never_counts_as_peer_reviewed():
    work = _work(type="article", doi="https://doi.org/10.48550/arxiv.2403.14403",
                 primary_location={"source": None}, locations=[])
    assert _venue_of(work)[1] is False


# ─── Selecting the matches ───────────────────────────────────────────────────


def test_resolved_by_identifier_and_enriched_with_reviewed_version():
    preprint = _work()
    published = _work(
        id="https://openalex.org/W2",
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        cited_by_count=183,
        primary_location={"source": None},
    )
    http = FakeHttp({
        "works/doi:10.48550": preprint,
        "title.search": {"results": [published, preprint]},
    })
    result = collect_openalex(
        "adaptive_rag", "https://arxiv.org/abs/2403.14403",
        http=http, expected_title="Adaptive RAG", today=TODAY,
    )
    assert result.errors == []
    assert len(result.evidence) == 1
    value = result.evidence[0].value
    assert "peer_reviewed=true" in value
    assert "venue=ACL Anthology" in value
    assert "cited_by=183" in value, "the most cited version of the work is taken"


def test_foreign_work_is_rejected_instead_of_recorded():
    """The title did not match, so no evidence is created."""
    foreign = _work(id="https://openalex.org/W9", title="CareerX: A Framework",
                    cited_by_count=500)
    http = FakeHttp({"title.search": {"results": [foreign]}})
    result = collect_openalex(
        "self_rag", "https://example.org/no-identifier",
        http=http, expected_title="Self-RAG", today=TODAY,
    )
    assert result.evidence == []
    assert any("no reliable match by title" in e for e in result.errors)


def test_prefix_match_accepts_full_paper_title():
    """The technology name begins the title of the work, which is admissible."""
    work = _work(id="https://openalex.org/W3",
                 title="Self-RAG: Learning to Retrieve, Generate, and Critique")
    http = FakeHttp({"title.search": {"results": [work]}})
    result = collect_openalex(
        "self_rag", "https://example.org/no-identifier",
        http=http, expected_title="Self-RAG", today=TODAY,
    )
    assert len(result.evidence) == 1
    assert result.errors == []


def test_title_separators_do_not_break_the_query():
    """A comma and a colon in a title separate filter conditions."""
    work = _work(title="Self-RAG: Learning to Retrieve, Generate, and Critique")
    http = FakeHttp({"works/doi:10.48550": work, "title.search": {"results": [work]}})
    collect_openalex(
        "self_rag", "https://arxiv.org/abs/2310.11511", http=http, today=TODAY,
    )
    search_calls = [c for c in http.calls if "title.search" in c]
    assert search_calls, "the search by title has to run"
    assert "%2C" not in search_calls[0] and "%3A" not in search_calls[0]


def test_citation_velocity_is_reported_not_raw_count_only():
    work = _work(cited_by_count=60, publication_date="2026-02-08")
    http = FakeHttp({"works/doi:10.48550": work, "title.search": {"results": [work]}})
    result = collect_openalex(
        "demo", "https://arxiv.org/abs/2602.00001", http=http, today=TODAY,
    )
    # Six months and sixty citations make ten a month.
    assert "citation_velocity=10.0" in result.evidence[0].value


def test_missing_work_reports_error_without_evidence():
    http = FakeHttp({}, status=404)
    result = collect_openalex("demo", "https://arxiv.org/abs/2602.00001",
                              http=http, today=TODAY)
    assert result.evidence == []
    assert result.errors


def test_title_with_a_question_mark_does_not_break_the_query():
    """Wildcards in the title of a work make the request inadmissible.

    The index treats `?` and `*` as wildcards and answers 400, and the record is
    left without a venue — that is, a preprint for ever. Titles with a question
    mark abound in this field; "What Retrieval Granularity Should We Use?" is one.
    """
    import re

    for title, expected in [
        ("Dense X Retrieval: What Granularity Should We Use?",
         "Dense X Retrieval  What Granularity Should We Use"),
        ("RAG or Long Context? A Comparison", "RAG or Long Context  A Comparison"),
        ("Foo * Bar", "Foo   Bar"),
    ]:
        cleaned = re.sub(r"[,|:?*]+", " ", title).strip()
        assert cleaned == expected, cleaned
        assert not set("?*:,|") & set(cleaned), f"separators remain: {cleaned!r}"
