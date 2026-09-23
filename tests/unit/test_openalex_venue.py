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


def test_the_archive_is_not_named_as_the_venue_of_a_reviewed_work():
    """A conference paper whose only named location is the preprint archive.

    The index often carries no venue for such a work while the work type and the
    publisher prefix say plainly that it was reviewed. The name of the archive
    then used to be written as the venue, giving "venue=arXiv (Cornell
    University); peer_reviewed=true": a contradiction on its face, which sends a
    reader checking the evidence to the archive instead of to the conference.
    """
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.52202/085713-1222",
        primary_location={"source": None},
        locations=[{"source": {"display_name": "arXiv (Cornell University)",
                               "type": "repository"}}],
    )
    venue, reviewed = _venue_of(work)
    assert reviewed is True, "the work type and the prefix say it was reviewed"
    assert "arxiv" not in venue.lower(), (
        f"the archive is named as the venue of a reviewed work: {venue!r}"
    )
    assert "10.52202" in venue, "what is known is the publisher prefix"


def test_a_known_publisher_still_wins_over_the_archive_name():
    """The other side: a recognised prefix keeps naming the venue."""
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2026.acl-long.1709",
        primary_location={"source": None},
        locations=[{"source": {"display_name": "arXiv (Cornell University)",
                               "type": "repository"}}],
    )
    assert _venue_of(work) == ("ACL Anthology", True)


def test_a_real_venue_name_is_not_discarded():
    """The other side again: a name that is not an archive is kept."""
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.52202/085713-1222",
        primary_location={"source": None},
        locations=[{"source": {"display_name": "Proceedings of Something",
                               "type": "conference"}}],
    )
    venue, reviewed = _venue_of(work)
    assert reviewed is True
    assert venue == "Proceedings of Something"


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


# ─── The title the preprint archive returned ─────────────────────────────────
#
# The index does not hold every preprint under its archive identifier. Until
# 2026-09-22 such a record was then searched by its name alone, and five records
# came back from every pass as refusals: three were found by name all the same,
# one ("Naive Dense", behind which stands Dense Passage Retrieval) begins no
# title and was never found although the index holds its EMNLP 2020 paper, and
# one the index lacks entirely.

DPR_TITLE = "Dense Passage Retrieval for Open-Domain Question Answering"


def _dpr(**kwargs) -> dict:
    return _work(**{
        "id": "https://openalex.org/W3015883388",
        "title": DPR_TITLE,
        "type": "conference-paper",
        "doi": "https://doi.org/10.18653/v1/2020.emnlp-main.550",
        "publication_date": "2020-11-01",
        "primary_location": {"source": None},
        **kwargs,
    })


def test_the_archive_title_finds_a_work_the_identifier_does_not():
    """The orchestrator hands the archive's title to the index.

    This is the bait for the whole change: on the code before it, the record
    below received no evidence from the index and two refusals instead.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import collect

    from services.registry import store
    from tests.support import FakeTransport, SourceBehaviour
    from tests.support.fake_transport import json_body

    entry = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        b"<id>http://arxiv.org/abs/2004.04906v3</id>"
        b"<published>2020-04-10T00:00:00Z</published>"
        b"<title>" + DPR_TITLE.encode() + b"</title>"
        b"<summary>A recorded answer.</summary></entry></feed>"
    )
    http = FakeTransport({
        "export.arxiv.org": SourceBehaviour(entry),
        # No route for the identifier lookup: the transport answers it with 404,
        # as the index answered for this preprint.
        "title.search:Dense%20Passage": SourceBehaviour(
            json_body({"results": [_dpr()]})
        ),
        "title.search:Naive%20Dense": SourceBehaviour(json_body({"results": []})),
    })
    tech = store.Technology(
        id="naive_dense", name="Naive Dense", kind="technique", groups=["C"],
        links=[store.Link(url="https://arxiv.org/abs/2004.04906", kind="preprint")],
    )

    raw, errors = collect._collect_one(tech, http=http, github_token=None, today=TODAY)

    from_index = [e for e in raw if "openalex.org" in e.source]
    assert len(from_index) == 1, f"the index gave nothing; refusals: {errors}"
    assert "peer_reviewed=true" in from_index[0].value
    assert "venue=ACL Anthology" in from_index[0].value
    assert [e for e in errors if e[0] == "openalex"] == []
    assert not http.calls_matching("title.search:Naive"), (
        "the name is searched although the title of the work was found"
    )


def test_an_unknown_identifier_is_no_refusal_when_the_title_finds_the_work():
    http = FakeHttp({"title.search": {"results": [_dpr()]}})
    result = collect_openalex(
        "naive_dense", "https://arxiv.org/abs/2004.04906", http=http,
        expected_title="Naive Dense", known_title=DPR_TITLE, today=TODAY,
    )
    assert len(result.evidence) == 1
    assert result.errors == []


def test_the_archive_title_must_match_exactly():
    """A longer title that begins with it is another work.

    The name of a record is matched by its beginning because a name is shorter
    than a title. The title of the work is the whole thing, and a work whose
    title merely begins with it is somebody else's.
    """
    other = _dpr(id="https://openalex.org/W7", title=f"{DPR_TITLE} in Vietnamese")
    http = FakeHttp({"title.search": {"results": [other]}})
    result = collect_openalex(
        "naive_dense", "https://arxiv.org/abs/2004.04906", http=http,
        expected_title="Naive Dense", known_title=DPR_TITLE, today=TODAY,
    )
    assert result.evidence == []


def test_the_name_remains_the_last_resort():
    """Where the title of the work finds nothing, the name works as before."""
    work = _work(id="https://openalex.org/W3",
                 title="Self-RAG: Learning to Retrieve, Generate, and Critique")

    class Routes(FakeHttp):
        def get(self, url, headers=None, timeout=20):
            self.calls.append(url)
            if "title.search:Self-RAG" in url and "Renamed" not in url:
                return (200, json.dumps({"results": [work]}).encode())
            return (404, b"{}")

    http = Routes({})
    result = collect_openalex(
        "self_rag", "https://arxiv.org/abs/2310.11511", http=http,
        expected_title="Self-RAG", known_title="Self-RAG Renamed Before Print",
        today=TODAY,
    )
    assert len(result.evidence) == 1


def test_an_unknown_identifier_is_named_once_when_nothing_is_found():
    """One record that is not found is one refusal, and it says why."""
    http = FakeHttp({"title.search": {"results": []}})
    result = collect_openalex(
        "msft_graphrag", "https://arxiv.org/abs/2404.16130", http=http,
        expected_title="Microsoft GraphRAG",
        known_title="From Local to Global: A Graph RAG Approach",
        today=TODAY,
    )
    assert result.evidence == []
    assert len(result.errors) == 1, result.errors
    assert "no work under 10.48550/arXiv.2404.16130" in result.errors[0]


def test_a_refusal_on_the_identifier_is_not_reported_as_an_absence():
    """A rate refusal leaves no work, and it is no answer about the work."""

    # The search answers with a work that matches nothing, so the collector
    # reaches the message about an unreliable match, which is where a refusal
    # would be misreported as an absence. With an empty answer it never got
    # there, and a mutation of this rule survived on 2026-09-22.
    stranger = _work(id="https://openalex.org/W8", title="Another Work Entirely")

    class Refusing(FakeHttp):
        def get(self, url, headers=None, timeout=20):
            self.calls.append(url)
            if "works/doi:" in url:
                return (429, b"")
            return (200, json.dumps({"results": [stranger]}).encode())

    result = collect_openalex(
        "demo", "https://arxiv.org/abs/2602.00001", http=Refusing({}),
        expected_title="Demo", known_title="Demo: A Title", today=TODAY,
    )
    assert any("answered 429" in e for e in result.errors)
    assert any("no reliable match" in e for e in result.errors)
    assert not any("no work under" in e for e in result.errors)



def test_a_reviewed_work_with_no_identifier_has_no_named_venue():
    """With no identifier there is no prefix to name.

    "DOI " with nothing after it was written as the venue.
    """
    work = _work(doi=None, type="conference-paper", primary_location={"source": None})
    assert _venue_of(work) == ("", True)


def test_a_refused_title_search_is_not_said_to_have_found_no_match():
    """Only a title the index answered for can have found no match.

    The live check of 2026-09-22 listed a title whose search had been refused
    with a 504 among those that "gave no reliable match".
    """

    class RefusingTheTitle(FakeHttp):
        def get(self, url, headers=None, timeout=20):
            self.calls.append(url)
            if "title.search:Dense" in url:
                return (504, b"")
            return (200, json.dumps({"results": []}).encode())

    result = collect_openalex(
        "naive_dense", "https://arxiv.org/abs/2004.04906", http=RefusingTheTitle({}),
        expected_title="Naive Dense", known_title=DPR_TITLE, today=TODAY,
    )
    assert any("answered 504" in e for e in result.errors)
    assert not any(DPR_TITLE in e for e in result.errors if "no reliable match" in e)
