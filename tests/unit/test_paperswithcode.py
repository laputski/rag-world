"""The works-and-code catalogue collector.

The catalogue is dangerous in exactly the way it is useful: it answers 200 to
almost anything. Some parameters it silently ignores, returning a feed of the
newest work in the field, and such an answer is indistinguishable from a
meaningful one. A collector satisfied by a 200 would attribute one work's evidence
to another, and would do it quietly.

The checks are built on recorded answers: two real entries (one with a publication
venue and a preprint without one) and a real week of the feed.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.collectors import paperswithcode as pwc  # noqa: E402
from tests.support import FakeTransport, SourceBehaviour, load_fixture  # noqa: E402

TODAY = date(2026, 8, 12)


def fixture(name: str) -> bytes:
    return load_fixture(name)


def routes(**overrides: SourceBehaviour) -> FakeTransport:
    base = {"paperswithcode.co": SourceBehaviour(fixture("pwc_paper_preprint.json"))}
    base.update(overrides)
    return FakeTransport(base)


# ─── The answer has to answer the question asked ─────────────────────────────


def test_paper_with_another_identifier_is_refused():
    """The catalogue answers an ignored parameter with a feed of the newest work.

    The answer looks meaningful: a 200, a familiar structure, real data. The only
    thing that does not match is what was asked for.
    """
    http = routes(**{"paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))})
    paper, error = pwc.fetch_paper("2405.14831", http=http)

    assert paper is None
    assert error and "answered about a different work" in error


def test_paper_with_the_requested_identifier_is_accepted():
    paper, error = pwc.fetch_paper("2405.14831", http=routes())
    assert error is None
    assert paper is not None
    assert paper.arxiv_id == "2405.14831"
    assert "HippoRAG" in paper.title


def test_absent_paper_is_not_an_error():
    """The catalogue having no such work is an answer, not a failure of the pass."""
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=404)})
    paper, error = pwc.fetch_paper("9999.99999", http=http)
    assert paper is None
    assert error is None


def test_broken_answer_does_not_raise():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour("{not json".encode())})
    paper, error = pwc.fetch_paper("2405.14831", http=http)
    assert paper is None
    assert error and "malformed answer" in error


def test_refusal_is_reported_not_swallowed():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    paper, error = pwc.fetch_paper("2405.14831", http=http)
    assert paper is None
    assert error and "503" in error


# ─── Evidence of the venue ───────────────────────────────────────────────────


def test_venue_becomes_evidence():
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))
    })
    result = pwc.collect_venue("rag_original", "2005.11401", http=http, today=TODAY)

    assert result.errors == []
    assert len(result.evidence) == 1
    item = result.evidence[0]
    assert item.type == "publication"
    assert "venue=NeurIPS" in item.value
    assert "peer_reviewed=true" in item.value
    assert item.source.startswith("https://paperswithcode.co/api/v1/papers/")
    assert item.fetched_at == TODAY


def test_preprint_without_a_venue_yields_no_evidence():
    """An absence of venue information is not information about an absent venue.

    Evidence of the publication type without a venue would assert exactly what the
    preprint already asserts, and would be counted a second time towards
    confidence.
    """
    result = pwc.collect_venue("hipporag", "2405.14831", http=routes(), today=TODAY)
    assert result.errors == []
    assert result.evidence == []


def test_citation_counter_is_named_in_the_value():
    """The catalogue counts citations differently from the open index.

    HippoRAG has nearly three hundred here and sixty-odd in the open index: two
    different counters of one work. Not naming the counter would give the reader
    two numbers under one name.
    """
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))
    })
    value = pwc.collect_venue("x", "2005.11401", http=http, today=TODAY).evidence[0].value
    assert "citations_semantic_scholar=" in value
    assert "cited_by=" not in value, (
        "the open index field name would mean the counter is the same one"
    )


def test_citation_count_does_not_enter_the_metric_series():
    """Attention is computed from one counter, or the quantities are incomparable.

    The rule takes the largest value across sources; two counters of one work under
    that rule would inflate attention systematically.
    """
    source = (ROOT / "services" / "collectors" / "paperswithcode.py").read_text(
        encoding="utf-8"
    )
    assert "MetricPoint" not in source
    assert "citation_velocity" not in source


# ─── The discovery feed ──────────────────────────────────────────────────────


def test_discovery_returns_the_week_of_papers():
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_discovery.json"))
    })
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))

    assert problems == []
    assert found, "the week of the feed is empty although the recorded answer has work"
    assert all(p.published >= date(2026, 8, 1) for p in found)
    assert all(p.arxiv_id for p in found)


def test_discovery_refuses_papers_older_than_asked():
    """The catalogue may not apply the date parameter, and the feed goes stale."""
    payload = json.loads(fixture("pwc_discovery.json"))
    payload["results"][0]["published"] = "2024-01-01T00:00:00Z"
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(json.dumps(payload).encode())
    })

    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))

    assert any("the date parameter was not applied" in p for p in problems)
    assert all(p.published >= date(2026, 8, 1) for p in found)


def test_discovery_survives_a_missing_list():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b'{"count": 3}')})
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))
    assert found == []
    assert problems and "without a list of works" in problems[0]


def test_empty_week_is_not_a_problem():
    """A week without new work is ordinary and deserves no complaint."""
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(b'{"count": 0, "results": []}')
    })
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))
    assert found == []
    assert problems == []


def test_discovery_asks_the_catalogue_by_method_and_date():
    """The request goes by method tag: a full-text search yields ten times the noise."""
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_discovery.json"))
    })
    pwc.discover(http=http, published_after=date(2026, 8, 1))

    asked = http.calls_matching("paperswithcode.co")
    assert len(asked) == 1
    assert "method=rag" in asked[0]
    assert "published_after=2026-08-01" in asked[0]


# ─── The host under the collection rule ──────────────────────────────────────


def test_catalogue_host_is_allowed():
    from services.collectors.base import is_allowed_host

    assert is_allowed_host(pwc.PWC_API)


def test_foreign_host_is_refused(monkeypatch):
    monkeypatch.setattr(pwc, "PWC_API", "https://example.org/api/v1")
    paper, error = pwc.fetch_paper("2405.14831", http=routes())
    assert paper is None
    assert error and "allowlist" in error


@pytest.mark.parametrize("venue,expected", [
    ("NeurIPS 2020 12", True),
    ("ICLR 2024", True),
    ("", False),
])
def test_venue_year_marks_peer_review(venue, expected):
    """A year in the proceedings name tells a real publication from a plan."""
    payload = json.loads(fixture("pwc_paper_with_venue.json"))
    payload["proceeding"] = venue
    parsed = pwc.parse_paper(payload)
    assert (parsed.venue is not None) == bool(venue)
    if venue:
        assert bool(pwc._VENUE_YEAR.search(parsed.venue)) is expected
