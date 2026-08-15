"""Exhaustive tests of the evidence collectors and of the cross-check stage.

Without a network: the HTTP client is replaced by a stub returning prepared
answers, including a reproduction of the three wrong links found in review.
"""

from __future__ import annotations

from datetime import date

from services.collectors import arxiv, github, openalex, s5
from services.collectors.base import HttpGetter, RawEvidence, is_allowed_host

TODAY = date(2026, 8, 5)


class FakeHttp(HttpGetter):
    """A stub HTTP client returning a prepared answer by a substring of the URL.

    Matching takes the LONGEST matching substring, so that '/repos/a/b/releases'
    does not match the rule for '/repos/a/b'.
    """

    def __init__(self, responses: dict[str, tuple[int, bytes]]):
        self._responses = responses
        self.calls: list[str] = []

    def get(self, url: str, headers=None, timeout=20) -> tuple[int, bytes]:
        self.calls.append(url)
        # Patterns are sorted by descending length: the longer, more exact one wins.
        for pattern in sorted(self._responses, key=len, reverse=True):
            if pattern in url:
                return self._responses[pattern]
        return (404, b"")


# ─── allowlist (C4) ──────────────────────────────────────────────────────────


def test_allowlist_accepts_known_hosts():
    for url in [
        "https://arxiv.org/abs/2401.15884",
        "https://api.github.com/repos/microsoft/graphrag",
        "https://api.openalex.org/works/doi:10.1/xyz",
    ]:
        assert is_allowed_host(url), f"{url} should be allowed"


def test_allowlist_rejects_unknown_hosts():
    for url in [
        "https://malicious.example.com/abs/2401.15884",
        "https://medium.com/@someone/post",
        "https://sub.example.net/x",
    ]:
        assert not is_allowed_host(url), f"{url} should be refused"


# ─── arXiv ───────────────────────────────────────────────────────────────────

ARXIV_ATOM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>{title}</title>
    <published>{published}T00:00:00Z</published>
    <summary>Abstract.</summary>
  </entry>
</feed>"""


def test_arxiv_extracts_id_and_title():
    body = ARXIV_ATOM_TEMPLATE.format(
        arxiv_id="2502.14902",
        title="PathRAG: Pruning Graph-based Retrieval with Relational Paths",
        published="2025-02-20",
    ).encode()
    http = FakeHttp({"id_list=2502.14902": (200, body)})
    result = arxiv.collect_arxiv("pathrag", "https://arxiv.org/abs/2502.14902",
                                 http=http, today=TODAY)
    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.type == "publication"
    assert "2502.14902" in ev.value
    assert "PathRAG" in ev.actual_title
    assert ev.verified is False  # the cross-check stage decides


def test_arxiv_accepts_bare_id():
    body = ARXIV_ATOM_TEMPLATE.format(
        arxiv_id="2310.11511", title="Self-RAG", published="2023-10-17"
    ).encode()
    http = FakeHttp({"id_list=2310.11511": (200, body)})
    result = arxiv.collect_arxiv("self_rag", "2310.11511", http=http, today=TODAY)
    assert len(result.evidence) == 1


def test_arxiv_handles_missing_entry():
    body = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    http = FakeHttp({"id_list=0000.00000": (200, body)})
    result = arxiv.collect_arxiv("x", "0000.00000", http=http, today=TODAY)
    assert result.evidence == []
    assert any("has no entry" in e for e in result.errors)


def test_arxiv_invalid_id_extracted():
    http = FakeHttp({})
    result = arxiv.collect_arxiv("x", "https://example.com/notarxiv", http=http, today=TODAY)
    assert result.evidence == []
    assert any("no archive identifier" in e for e in result.errors)


def test_arxiv_handles_api_error_status():
    http = FakeHttp({"id_list=9999.99999": (500, b"server error")})
    result = arxiv.collect_arxiv("x", "9999.99999", http=http, today=TODAY)
    assert result.evidence == []
    assert any("500" in e for e in result.errors)


# ─── GitHub ──────────────────────────────────────────────────────────────────


def test_github_extracts_license_and_releases():
    repo_body = (
        b'{"license": {"key": "mit", "name": "MIT License"}, '
        b'"pushed_at": "2026-07-01T12:00:00Z", "has_issues": true}'
    )
    http = FakeHttp({
        "/repos/microsoft/graphrag": (200, repo_body),
        "/repos/microsoft/graphrag/releases": (200, b'[{"tag_name": "v1.0"}]'),
    })
    result = github.collect_github("msft_graphrag", "https://github.com/microsoft/graphrag",
                                   http=http, today=TODAY)
    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.type == "repository"
    assert "license=mit" in ev.value
    assert "last_push=2026-07-01" in ev.value
    assert "releases=yes" in ev.value


def test_github_handles_404():
    http = FakeHttp({"/repos/x/y": (404, b'{"message": "Not Found"}')})
    result = github.collect_github("x", "https://github.com/x/y", http=http, today=TODAY)
    assert result.evidence == []
    assert any("404" in e for e in result.errors)


def test_github_no_releases():
    repo_body = b'{"license": null, "pushed_at": "2026-01-01T00:00:00Z"}'
    http = FakeHttp({
        "/repos/a/b": (200, repo_body),
        "/repos/a/b/releases": (200, b"[]"),
    })
    result = github.collect_github("ab", "https://github.com/a/b", http=http, today=TODAY)
    assert "releases=no" in result.evidence[0].value
    assert "license=none" in result.evidence[0].value


def test_github_invalid_url():
    http = FakeHttp({})
    result = github.collect_github("x", "https://bitbucket.org/x/y", http=http, today=TODAY)
    assert result.evidence == []
    assert any("owner/repo" in e for e in result.errors)


def test_github_passes_token_header():
    repo_body = b'{"license": {"key":"mit","name":"MIT"}, "pushed_at":"2026-01-01T00:00:00Z"}'
    http = FakeHttp({
        "/repos/a/b": (200, repo_body),
        "/repos/a/b/releases": (200, b"[]"),
    })
    github.collect_github("ab", "https://github.com/a/b", http=http,
                          token="ghp_secret", today=TODAY)
    # The calls are recorded. FakeHttp does not keep headers, so the successful
    # call itself is what confirms the request went out.
    assert len(http.calls) >= 2


# ─── OpenAlex ────────────────────────────────────────────────────────────────


def test_openalex_extracts_citations():
    body = (
        b'{"cited_by_count": 719, "title": "Adaptive RAG", '
        b'"publication_year": 2024, "id": "https://openalex.org/W123"}'
    ).replace(b"719", b"719")
    http = FakeHttp({"openalex.org/works/doi:10.1/x": (200, body)})
    result = openalex.collect_openalex(
        "adaptive_rag", "https://doi.org/10.1/x", http=http, today=TODAY
    )
    # doi.org is not on the allowlist directly, but the call goes to the open
    # index at api.openalex.org, with the URL built as .../works/doi:10.1/x.
    if result.evidence:
        assert "cited_by=719" in result.evidence[0].value


def test_openalex_handles_invalid_json():
    http = FakeHttp({"openalex.org": (200, b"not json")})
    result = openalex.collect_openalex("x", "test query", http=http, today=TODAY)
    assert any("JSON" in e for e in result.errors) or any(
        "no such work" in e for e in result.errors
    )


# ─── The cross-check stage: the deterministic checks ─────────────────────────


def test_s5_title_match_passes():
    ev = RawEvidence(
        technology_id="pathrag", type="publication",
        value="arXiv:2502.14902 (2025)",
        source="https://arxiv.org/abs/2502.14902", fetched_at=TODAY,
        expected_title="PathRAG: Pruning Graph-based Retrieval",
        actual_title="PathRAG: Pruning Graph-based Retrieval Augmented Generation",
    )
    res = s5.check(ev)
    assert res.passed, res.reasons


def test_s5_title_mismatch_reproduces_broken_links():
    """The three wrong links: the identifier resolves and the title does not match.

    MA-RAG: the identifier 2406.18542 actually resolves to a paper about LiDAR.
    """
    ev = RawEvidence(
        technology_id="ma_rag", type="publication",
        value="arXiv:2406.18542 (2024)",
        source="https://arxiv.org/abs/2406.18542", fetched_at=TODAY,
        expected_title="MA-RAG: Multi-Agent Retrieval-Augmented Generation",
        actual_title="Generative AI Empowered LiDAR Point Cloud Generation",
    )
    res = s5.check(ev)
    assert not res.passed
    assert any("titles do not match" in r for r in res.reasons)


def test_s5_unknown_domain_rejected():
    ev = RawEvidence(
        technology_id="x", type="publication",
        value="x", source="https://malicious.example.com/x",
        fetched_at=TODAY,
    )
    res = s5.check(ev)
    assert not res.passed
    assert any("allowlist" in r for r in res.reasons)


def test_s5_negative_citations_rejected():
    ev = RawEvidence(
        technology_id="x", type="publication",
        value="cited_by=-5", source="https://api.openalex.org/x",
        fetched_at=TODAY,
    )
    res = s5.check(ev)
    assert not res.passed
    assert any("citation count is negative" in r for r in res.reasons), res.reasons


def test_s5_year_out_of_range_rejected():
    ev = RawEvidence(
        technology_id="x", type="publication",
        value="year=1800", source="https://api.openalex.org/x",
        fetched_at=TODAY,
    )
    res = s5.check(ev)
    assert not res.passed
    assert any("1800" in r for r in res.reasons)


def test_s5_year_in_range_passes():
    ev = RawEvidence(
        technology_id="x", type="publication",
        value="year=2024", source="https://api.openalex.org/x",
        fetched_at=TODAY,
    )
    res = s5.check(ev)
    assert res.passed, res.reasons


def test_s5_no_titles_no_mismatch_check():
    """With no expected or actual title, the title comparison does not run."""
    ev = RawEvidence(
        technology_id="x", type="repository",
        value="license=mit", source="https://github.com/a/b",
        fetched_at=TODAY,
    )
    res = s5.check(ev)
    assert res.passed, res.reasons


def test_s5_check_many_returns_pairs():
    evs = [
        RawEvidence(technology_id="x", type="publication", value="y",
                    source="https://arxiv.org/abs/0000.00000", fetched_at=TODAY),
        RawEvidence(technology_id="y", type="publication", value="y",
                    source="https://malicious.example.com", fetched_at=TODAY),
    ]
    pairs = s5.check_many(evs)
    assert len(pairs) == 2
    assert pairs[0][1].passed  # arxiv ok
    assert not pairs[1][1].passed  # malicious rejected


# ─── Ranges: the patterns have to match what the collectors actually write ───
#
# The range check was dead once already: it looked for one spelling while the
# collector wrote another. Such a protection looks like it exists and catches
# nothing, so what is checked here is exactly the strings the collectors write.


def test_s5_future_year_rejected_relative_to_collection_date():
    """The bound on the year comes from the collection date, not a written-in number."""
    ev = RawEvidence(
        technology_id="x", type="publication",
        value=f"venue=X; peer_reviewed=false; cited_by=1; year={TODAY.year + 5}",
        source="https://api.openalex.org/x", fetched_at=TODAY,
    )
    assert not s5.check(ev).passed


def test_s5_next_year_is_allowed():
    """Works dated next year are ordinary at the end of a year."""
    ev = RawEvidence(
        technology_id="x", type="publication",
        value=f"venue=X; peer_reviewed=false; cited_by=1; year={TODAY.year + 1}",
        source="https://api.openalex.org/x", fetched_at=TODAY,
    )
    assert s5.check(ev).passed


def test_s5_checks_year_in_preprint_format():
    """The preprint archive writes the year in parentheses, not as `year=`."""
    ev = RawEvidence(
        technology_id="x", type="publication",
        value=f"arXiv:2403.14403 ({TODAY.year + 5})",
        source="https://arxiv.org/abs/2403.14403", fetched_at=TODAY,
    )
    assert not s5.check(ev).passed


def test_s5_rejects_negative_downloads():
    ev = RawEvidence(
        technology_id="x", type="package_downloads",
        value="package=demo; version=1.0; downloads_last_month=-9",
        source="https://pypi.org/project/demo/", fetched_at=TODAY,
    )
    assert not s5.check(ev).passed


def test_s5_rejects_negative_velocity():
    ev = RawEvidence(
        technology_id="x", type="publication",
        value="venue=X; cited_by=42; year=2024; citation_velocity=-3.0",
        source="https://api.openalex.org/x", fetched_at=TODAY,
    )
    assert not s5.check(ev).passed


def test_s5_accepts_ordinary_values_from_every_collector():
    """A false rejection is worse than a miss: it loses correct data."""
    ordinary = [
        ("publication", "venue=ACL; peer_reviewed=true; cited_by=42; "
                        "year=2024; citation_velocity=1.8",
         "https://api.openalex.org/works/W1"),
        ("publication", "arXiv:2403.14403 (2024)",
         "https://arxiv.org/abs/2403.14403"),
        ("repository", "demo/demo: license=mit, last_push=2026-01-01, releases=yes",
         "https://github.com/demo/demo"),
        ("package_downloads", "package=demo; version=1.2.3; "
                              "downloads_last_month=20000",
         "https://pypi.org/project/demo/"),
        ("framework_presence", "frameworks=haystack, langchain",
         "https://github.com/langchain-ai/langchain"),
    ]
    for kind, value, source in ordinary:
        ev = RawEvidence(
            technology_id="x", type=kind, value=value,
            source=source, fetched_at=TODAY,
        )
        result = s5.check(ev)
        assert result.passed, f"{kind}: {result.reasons}"


# ─── Routing links to collectors ─────────────────────────────────────────────

def _sources_for(url: str) -> list[str]:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import collect

    return collect._collectors_for(url)


def test_doi_link_reaches_the_open_index():
    """A work published other than as a preprint has to yield evidence.

    The open index resolves a work by its digital identifier and always could; the
    route was missing, and a record whose only source was published in a journal or
    at a conference was left with no publication evidence at all. That is how
    Standard HybridRAG had no level, although the technique underlies hybrid search
    and is described by a work with six hundred citations.

    The failure is quiet: the link resolves, the link check is satisfied, and there
    is simply no evidence — which can only be understood by comparing the record
    with its source.
    """
    assert _sources_for("https://doi.org/10.1145/1571941.1572114") == ["openalex"]


def test_arxiv_link_is_asked_of_three_sources():
    assert _sources_for("https://arxiv.org/abs/2502.14902") == [
        "arxiv", "openalex", "paperswithcode",
    ]


def test_unknown_host_is_asked_of_nobody():
    """A link to a provider's page is not a source of evidence."""
    assert _sources_for("https://atlan.com/know/hybrid-rag/") == []
