"""The third route of discovery: the archive asked directly.

The other two routes depend on somebody having classified a work first, by a tag
or by putting it in a list. This one asks the archive by category and by the
phrases that name the subject, and so sees work nobody has classified yet. That
is what it is for: a record was entered by hand because no tag and no list held
it, and a queue that misses such work misses exactly the new thing.

Everything here is checked against a recorded answer. A test that asked the real
archive would pass or fail by what somebody published this morning, and would
stop being read within a month.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.collectors.arxiv_feed import (  # noqa: E402
    build_query,
    discover_from_archive,
)
from tests.support import FakeTransport, SourceBehaviour  # noqa: E402


def entry(arxiv_id: str, title: str, published: str, summary: str = "An abstract.") -> str:
    return f"""
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>{title}</title>
    <published>{published}T00:00:00Z</published>
    <summary>{summary}</summary>
  </entry>"""


def feed(*entries: str) -> bytes:
    body = "".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'
    ).encode()


NAMED = entry("2608.30163", "Doc-REFRAG: Rethinking Multimodal Document Retrieval",
              "2026-08-31", "We index pages and rerank passages over a corpus.")
UNNAMED = entry("2608.31139", "Configurable Semantic Chunking for Biomedical Extraction",
                "2026-08-31")
OLD = entry("2501.00001", "OldRAG: A Work From Long Ago", "2025-01-01")

WINDOW = date(2026, 8, 25)


def routes(body: bytes = None, status: int = 200) -> dict[str, SourceBehaviour]:
    return {"export.arxiv.org": SourceBehaviour(
        body=body if body is not None else feed(NAMED, UNNAMED, OLD), status=status
    )}


# ─── What the route asks ─────────────────────────────────────────────────────


def test_the_query_asks_by_category_and_by_phrase_in_the_abstract():
    """A full-text match returns every work that mentions retrieval in passing."""
    query = build_query()
    assert "cat:cs.IR" in query and "cat:cs.CL" in query and "cat:cs.AI" in query
    assert 'abs:"retrieval-augmented generation"' in query
    assert "all:" not in query, "a full-text search returns the field at large"


def test_the_abstract_comes_from_the_same_answer():
    """One request, not one per work: the feed already carries the abstracts."""
    http = FakeTransport(routes())
    papers, _, _ = discover_from_archive(http=http, published_after=WINDOW)
    assert len(http.calls_matching("export.arxiv.org")) == 1
    assert papers and papers[0].abstract


# ─── What it returns and what it drops ───────────────────────────────────────


def test_a_named_work_inside_the_window_is_returned():
    papers, problems, _ = discover_from_archive(
        http=FakeTransport(routes()), published_after=WINDOW)
    assert [p.arxiv_id for p in papers] == ["2608.30163"]
    assert problems == []


def test_a_work_that_does_not_name_itself_is_discarded_not_refused():
    """The registry holds named technologies, and an unnamed work is not a failure.

    Of forty works matched in one week, twenty-one had no name in the title, and
    they were studies and applications. Counting them as refusals would say the
    archive had failed twenty-one times in a week when it had answered once.
    """
    papers, problems, discarded = discover_from_archive(
        http=FakeTransport(routes()), published_after=WINDOW)
    assert "2608.31139" not in [p.arxiv_id for p in papers]
    assert any("does not name itself" in d for d in discarded)
    assert problems == []


def test_a_work_older_than_the_window_is_not_returned():
    papers, _, _ = discover_from_archive(
        http=FakeTransport(routes()), published_after=WINDOW)
    assert "2501.00001" not in [p.arxiv_id for p in papers]


def test_an_entry_without_a_date_is_discarded():
    body = feed('<entry><id>http://arxiv.org/abs/2608.1v1</id>'
                "<title>NoDate: A Work</title><summary>x</summary></entry>")
    papers, problems, discarded = discover_from_archive(
        http=FakeTransport(routes(body)), published_after=WINDOW)
    assert papers == []
    assert any("without an identifier or a date" in d for d in discarded)
    assert problems == []


# ─── When the archive misbehaves ─────────────────────────────────────────────


def test_a_refusal_of_the_request_is_reported_as_a_refusal():
    papers, problems, discarded = discover_from_archive(
        http=FakeTransport(routes(b"", status=503)), published_after=WINDOW)
    assert papers == []
    assert problems and "503" in problems[0]
    assert discarded == []


def test_an_answer_with_no_entries_is_reported_and_not_taken_for_an_empty_week():
    papers, problems, discarded = discover_from_archive(
        http=FakeTransport(routes(feed())), published_after=WINDOW)
    assert papers == []
    assert discarded, "silence must reach the caller rather than pass for an empty week"


def test_truncation_is_reported_when_the_window_was_not_covered():
    """The answer filled the cap and never reached the far edge of the window.

    Both halves matter. The archive always holds more matching work than the cap,
    so reporting on the cap alone would raise the alarm on every pass and so
    raise it on none.
    """
    body = feed(*[entry(f"2608.{n:05d}", f"Work{n}: A Named Thing", "2026-08-31")
                  for n in range(3)])
    papers, problems, _ = discover_from_archive(
        http=FakeTransport(routes(body)), published_after=WINDOW, max_results=3)
    assert len(papers) == 3
    assert problems and "without reaching" in problems[0]


def test_a_covered_window_is_not_reported_as_truncated():
    """The other side: an alarm on every pass is an alarm on none."""
    body = feed(entry("2608.30163", "Doc-REFRAG: A Named Thing", "2026-08-31"), OLD)
    papers, problems, _ = discover_from_archive(
        http=FakeTransport(routes(body)), published_after=WINDOW, max_results=2)
    assert len(papers) == 1
    assert problems == [], f"the window was covered to its edge: {problems}"
