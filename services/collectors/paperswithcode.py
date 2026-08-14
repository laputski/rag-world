"""The works-and-code catalogue: a publication venue and a feed of new work.

The catalogue gives two things the other sources do not.

**A second source for the peer-review level.** The publication venue used to
come from the open index alone, and an error there was covered by nothing. Here
it comes from a catalogue people maintain. Venue data is sparse: most preprints
have none, and then no evidence is created. That is right — the absence of
information is not information about an absence.

**A feed for discovering new work.** The method tag in the catalogue is applied
by people, and the density of the signal changes by an order of magnitude
because of it: a week of the `rag` tag yields about five works, whereas a
full-text search of the preprint archive yields about fifty, most of them
applications rather than architectures. Five candidates take a person a minute
to look through.

**The answer is checked for answering the question that was asked.** The
catalogue has parameters it silently ignores: `q`, `arxiv_id`, `title`,
`ordering`. A request carrying them answers 200 and a feed of the newest work in
the whole field, and such an answer is indistinguishable from a meaningful one.
So it is checked here that the work returned carries the identifier requested,
and that the works of a feed are no older than the date requested. Without that
check the collector would silently attribute one work's evidence to another.

The catalogue is run by the community after paperswithcode.com closed. Its
longevity is unproven, so a refusal from it is handled like a refusal from any
other source: the pass continues and the refusal reaches the log.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

PWC_API = "https://paperswithcode.co/api/v1"

#: The method tag under which the catalogue gathers work on RAG.
RAG_METHOD = "rag"

#: What marks a peer-reviewed venue in the proceedings field. The catalogue
#: writes a string there of the form "NeurIPS 2020 12": a venue and a year.
_VENUE_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class Paper:
    """A catalogue entry reduced to what the portal needs of it."""

    arxiv_id: str
    title: str
    #: The abstract as the catalogue gives it. There is nothing to paraphrase:
    #: the abstract is already a summary, written by the authors.
    abstract: str
    published: date | None
    venue: str | None
    citations: int | None
    url: str
    repositories: list[str] = field(default_factory=list)
    #: The task tags of the catalogue, applied by people. A candidate's fitness
    #: for the registry is judged from them, and keeping them allows the
    #: judgement to be recomputed without asking the catalogue again.
    tasks: list[str] = field(default_factory=list)


def _paper_url(arxiv_id: str) -> str:
    return f"{PWC_API}/papers/{arxiv_id}"


def _get_json(http: HttpGetter, url: str) -> tuple[dict | None, str | None]:
    if not is_allowed_host(url):
        return None, f"host outside the allowlist: {url}"
    status, body = http.get(url, timeout=30)
    if status == 404:
        return None, None  # the catalogue has no such work: an answer, not a failure
    if status != 200:
        return None, f"status {status} from {url}"
    try:
        return json.loads(body), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"malformed answer from {url}"


def _as_date(value: object) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _venue_of(payload: dict) -> str | None:
    """The publication venue, when the catalogue knows it.

    There are three fields and usually no more than one of them is filled. An
    empty field means the information is missing, not that the work was never
    published: Self-RAG was accepted at a conference and has nothing here.
    """
    for key in ("proceeding", "conference_name", "conference"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_paper(payload: dict) -> Paper | None:
    """Reduce a catalogue entry to the shape the portal needs."""
    arxiv_id = payload.get("arxiv_id")
    title = payload.get("title")
    if not isinstance(arxiv_id, str) or not isinstance(title, str):
        return None
    repos = payload.get("repositories")
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=payload.get("abstract") if isinstance(payload.get("abstract"), str) else "",
        published=_as_date(payload.get("published")),
        venue=_venue_of(payload),
        citations=(
            payload["citation_count"]
            if isinstance(payload.get("citation_count"), int)
            else None
        ),
        url=_paper_url(arxiv_id),
        repositories=[
            r.get("url") for r in repos
            if isinstance(r, dict) and isinstance(r.get("url"), str)
        ] if isinstance(repos, list) else [],
        tasks=[
            t.get("slug") for t in payload.get("tasks") or []
            if isinstance(t, dict) and isinstance(t.get("slug"), str)
        ],
    )


def fetch_paper(
    arxiv_id: str, *, http: HttpGetter
) -> tuple[Paper | None, str | None]:
    """The catalogue entry for a preprint identifier.

    Returns the work and the reason for a refusal. The work returned must carry
    exactly the identifier requested: the catalogue answers a request with
    ignored parameters by a feed of the newest work, and such an answer looks
    meaningful.
    """
    payload, error = _get_json(http, _paper_url(arxiv_id))
    if error or payload is None:
        return None, error
    paper = parse_paper(payload)
    if paper is None:
        return None, f"the catalogue returned an entry without required fields: {arxiv_id}"
    if paper.arxiv_id != arxiv_id:
        return None, (
            f"the catalogue answered about a different work: {arxiv_id} was "
            f"asked for, {paper.arxiv_id} came back"
        )
    return paper, None


def collect_venue(
    technology_id: str,
    arxiv_id: str,
    *,
    http: HttpGetter,
    today: date | None = None,
) -> CollectResult:
    """Evidence of the publication venue, taken from the catalogue.

    The citation count is written into the evidence but **not** into the series
    of measurements. Attention on the map is normalised inside an age subgroup,
    and a subgroup is computed from one counter. Mixing two counters of one work
    would mean comparing what is not comparable, and a rule of taking the larger
    across sources would also inflate the result systematically. The counter is
    named inside the value so that a reader sees whose number it is.
    """
    today = today or date.today()
    result = CollectResult(source_name="paperswithcode", technology_id=technology_id)

    paper, error = fetch_paper(arxiv_id, http=http)
    if error:
        result.errors.append(error)
        return result
    if paper is None:
        return result  # the catalogue has no such work
    if not paper.venue:
        # There is no venue. Evidence of the publication type without one would
        # assert exactly what the preprint already asserts.
        return result

    peer_reviewed = bool(_VENUE_YEAR.search(paper.venue))
    parts = [f"venue={paper.venue}", f"peer_reviewed={str(peer_reviewed).lower()}"]
    if paper.citations is not None:
        parts.append(f"citations_semantic_scholar={paper.citations}")
    if paper.published:
        parts.append(f"year={paper.published.year}")

    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value="; ".join(parts),
        source=paper.url,
        fetched_at=today,
        expected_title=None,
        actual_title=paper.title,
    ))
    return result


def discover(
    *,
    http: HttpGetter,
    published_after: date,
    method: str = RAG_METHOD,
) -> tuple[list[Paper], list[str]]:
    """Work under the method tag published no earlier than the given date.

    Returns what was found and the reasons for refusals. Work older than the
    date requested is dropped with an explanation: the catalogue silently
    ignores some parameters, and a feed of the newest work in the whole field is
    indistinguishable from an answer to the point. An empty feed is legitimate,
    though: a week without new work happens.
    """
    query = urlencode({"method": method, "published_after": published_after.isoformat()})
    payload, error = _get_json(http, f"{PWC_API}/papers/?{query}")
    if error or payload is None:
        return [], [error] if error else []

    rows = payload.get("results")
    if not isinstance(rows, list):
        return [], [f"the catalogue returned a feed without a list of works: {type(rows).__name__}"]

    found: list[Paper] = []
    problems: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        paper = parse_paper(row)
        if paper is None:
            continue
        if paper.published is None:
            problems.append(f"a work without a date of publication: {paper.arxiv_id}")
            continue
        if paper.published < published_after:
            problems.append(
                f"the catalogue returned a work from {paper.published.isoformat()} "
                f"for a request from {published_after.isoformat()}: the date "
                f"parameter was not applied"
            )
            continue
        found.append(paper)
    return found, problems
