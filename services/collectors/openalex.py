"""The open-index collector: the publication venue and the citations.

The open index of scholarly works supplies two things:

* **the class of the venue** — a peer-reviewed conference or journal as against
  a preprint. This is the only machine-readable route to the level that requires
  peer review: without it every work stays a preprint, however well known its
  result;
* **citations and the date of publication**, from which the citation velocity is
  derived, that is, attention. The absolute citation count never reaches the
  views: it is out of date the moment it is measured and it is not comparable
  across fields.

The search runs in two steps. The work is first found by its preprint identifier
through that identifier's canonical digital object identifier. Its other
versions are then found by title, because the preprint and the conference
publication are two separate records of the index and peer review is visible
only on the second.

No language model takes part: every decision is made from fields of the answer.
"""

from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import quote

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

OPENALEX_API = "https://api.openalex.org"

#: The index meters requests in credits per day and ignores a contact address.
#:
#: It used to keep a "polite" pool for callers who gave one, and this collector
#: sent an address from the environment to get into it. The pool was retired in
#: February 2026. Observed on 2026-09-23: with and without an address the index
#: answered with the same limit of 1000 credits a day and spent them from the
#: same allowance. A lookup by identifier costs nothing and a filtered search
#: one credit, so a weekly pass stays far inside the anonymous limit and needs
#: no key either.

_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(?P<id>\d{4}\.\d{4,5})", re.I)
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")

#: Venue types that mean peer review. The type `repository` denotes a preprint
#: archive and confirms no review.
PEER_REVIEWED_SOURCE_TYPES = frozenset({"journal", "conference", "book series"})

#: Work types that mean peer review. A preprint has a type of its own, so the
#: distinction holds even when the venue name is not filled in.
PEER_REVIEWED_WORK_TYPES = frozenset({
    "article", "conference-paper", "proceedings-article", "book-chapter", "review",
})

#: Venues that look like a journal by type yet mean no review. The comparison is
#: by substring: the index calls the archive "arXiv (Cornell University)".
NOT_PEER_REVIEWED_MARKERS = ("arxiv", "biorxiv", "medrxiv", "ssrn", "preprint")

#: The prefix of a digital object identifier names the publisher unambiguously.
#: That rescues the case where the index left the venue name empty, which happens
#: often for conference publications while the venue is what the level turns on.
DOI_PREFIX_VENUES: dict[str, str] = {
    "10.18653": "ACL Anthology",
    "10.1145": "ACM",
    "10.1109": "IEEE",
    "10.1038": "Nature Portfolio",
    "10.1162": "MIT Press",
    "10.1609": "AAAI",
    "10.24963": "IJCAI",
    "10.14778": "VLDB Endowment",
    "10.1007": "Springer",
    "10.1016": "Elsevier",
    "10.1093": "Oxford University Press",
}

#: The identifier prefix of the preprint archive, which means no review.
PREPRINT_DOI_PREFIX = "10.48550"


def _is_preprint_venue(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in NOT_PEER_REVIEWED_MARKERS)


def _doi_prefix(work: dict) -> str:
    doi = (work.get("doi") or "").lower()
    match = re.search(r"(10\.\d{4,9})/", doi)
    return match.group(1) if match else ""


def _get_json(
    http: HttpGetter,
    url: str,
    result: CollectResult,
    *,
    absence_is_an_answer: bool = False,
) -> dict | None:
    if not is_allowed_host(url):
        result.skipped.append(f"host outside the allowlist: {url}")
        return None
    status, body = http.get(
        url, headers={"User-Agent": "rag-world/0.2 (registry collector)"}, timeout=20
    )
    # A lookup by identifier answered with 404 says that the index holds no work
    # under that identifier. That is information, and the caller decides what it
    # means once the search by title has run; counted as a refusal, it made five
    # records look refused every week while three of them were found by title in
    # the same request.
    if status == 404 and absence_is_an_answer:
        return None
    if status != 200:
        result.errors.append(f"the open index answered {status}")
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        result.errors.append("the open index answered malformed JSON")
        return None


def _venue_of(work: dict) -> tuple[str, bool]:
    """The name of the venue and whether it means peer review.

    The decision uses three signals in order of reliability: the venue type in
    the index, the type of the work itself, and the publisher prefix of the
    identifier. The latter two are needed because for some conference
    publications the index simply has no venue name, and on the first signal
    alone they would look like preprints.
    """
    prefix = _doi_prefix(work)
    work_type = (work.get("type") or "").strip().lower()
    is_preprint_doi = prefix == PREPRINT_DOI_PREFIX

    best_name = ""
    for location in [work.get("primary_location") or {}, *(work.get("locations") or [])]:
        source = (location or {}).get("source") or {}
        name = (source.get("display_name") or "").strip()
        source_type = (source.get("type") or "").strip().lower()
        if not name:
            continue
        if _is_preprint_venue(name):
            best_name = best_name or name
            continue
        if source_type in PEER_REVIEWED_SOURCE_TYPES:
            return name, True
        best_name = best_name or name

    if not is_preprint_doi and work_type in PEER_REVIEWED_WORK_TYPES:
        # The name of a preprint archive must not stand as the venue of a
        # reviewed work. `best_name` keeps such a name as a last resort, and on
        # this path it used to win over the publisher prefix, producing the value
        # "venue=arXiv (Cornell University); peer_reviewed=true": a contradiction
        # on its face, which sends a reader checking the evidence to the archive
        # instead of to the conference. The review itself is not in doubt here,
        # the work type and the publisher prefix say so; only the name was wrong.
        named = "" if _is_preprint_venue(best_name) else best_name
        # With no identifier at all there is no prefix to name, and "DOI " with
        # nothing after it was written as the venue. The caller writes an
        # empty venue as unknown.
        venue = DOI_PREFIX_VENUES.get(prefix) or named or (f"DOI {prefix}" if prefix else "")
        return venue, True

    return best_name, False


def _citation_velocity(work: dict, today: date) -> float | None:
    """Citations divided by the number of months since publication."""
    cited = work.get("cited_by_count")
    published = work.get("publication_date") or ""
    if cited is None or not published:
        return None
    try:
        year, month = int(published[:4]), int(published[5:7])
    except (ValueError, IndexError):
        return None
    months = (today.year - year) * 12 + (today.month - month)
    if months < 1:
        months = 1
    return round(cited / months, 3)


def collect_openalex(
    technology_id: str,
    query: str,
    *,
    http: HttpGetter,
    expected_title: str | None = None,
    known_title: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Collect the venue, whether it was reviewed, and the citations.

    `query` is a preprint address, an identifier or the title of a work. The
    result is evidence of the publication type; the citation figures go into the
    value field, from which the orchestrator takes them for the time series.

    `expected_title` is the name of the technology, which usually begins the
    title of its work. `known_title` is the title of the work itself, as another
    source returned it by identifier; it is tried first when the index does not
    resolve the identifier.
    """
    today = today or date.today()
    result = CollectResult(source_name="openalex", technology_id=technology_id)

    work: dict | None = None

    # A preprint has a canonical identifier, which is the most reliable key.
    arxiv_match = _ARXIV_RE.search(query)
    doi_match = _DOI_RE.search(query)
    identifier = ""
    if arxiv_match:
        identifier = f"10.48550/arXiv.{arxiv_match.group('id')}"
    elif doi_match:
        identifier = doi_match.group(0)
    # Whether the index answered that it holds no work under the identifier. A
    # refusal on rate also leaves no work, and saying "the index has no such
    # work" of it would state an absence nobody observed.
    absent = False
    if identifier:
        refusals = len(result.errors)
        work = _get_json(
            http, f"{OPENALEX_API}/works/doi:{identifier}", result,
            absence_is_an_answer=True,
        )
        absent = work is None and len(result.errors) == refusals

    def _norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _title_of(candidate: dict) -> str:
        return (candidate.get("title") or candidate.get("display_name") or "").strip()

    def _search_by_title(title: str) -> list[dict]:
        # Inside a filter the comma and the vertical bar separate conditions,
        # the colon separates a filter name from its value, and the question
        # mark and the asterisk stand for wildcards. Titles of works contain
        # them constantly: "What Retrieval Granularity Should We Use?" broke the
        # request with a 400, and the work silently stayed without a venue.
        #
        # The separators are replaced by a space. Word search does not suffer
        # from that, and the request stops being inadmissible.
        safe_title = re.sub(r"[,|:?*]+", " ", title).strip()
        attempted.append(title)
        refusals = len(result.errors)
        search = _get_json(
            http,
            f"{OPENALEX_API}/works?filter=title.search:{quote(safe_title)}&per_page=25",
            result,
        )
        # Only a title the index answered for can be said to have found no
        # match. A refused search is counted as a refusal, and naming it among
        # the titles that "gave no reliable match" stated an outcome of a
        # search that never ran; the live check of 2026-09-22 did exactly that
        # on a 504.
        if len(result.errors) == refusals:
            answered.append(title)
        return (search or {}).get("results") or []

    # The second step: the preprint and the conference publication are separate
    # records, and peer review is visible only on the second. A title carries
    # more authority the closer it comes from the work itself, so the titles are
    # tried in that order, and each later one only when the earlier found
    # nothing:
    #
    # * the title the index resolved from the identifier, matched exactly;
    # * the title the preprint archive returned for the same identifier, matched
    #   exactly. The index does not hold every preprint under its archive
    #   identifier, and without this step such a record was searched by its
    #   name alone. "Naive Dense" begins no title, and the work behind it, Dense
    #   Passage Retrieval, which the index holds as an EMNLP 2020 paper, was
    #   never found;
    # * the technology's name, which must begin the title: "Self-RAG" fits
    #   "Self-RAG: Learning to Retrieve...", and does not fit an unrelated work
    #   that merely mentions it.
    resolved_title = _title_of(work) if work else ""
    candidates: list[dict] = [work] if work else []
    matched: list[dict] = []
    attempted: list[str] = []
    answered: list[str] = []
    if resolved_title:
        candidates += _search_by_title(resolved_title)
        wanted = _norm(resolved_title)
        matched = [c for c in candidates if _norm(_title_of(c)) == wanted]
    else:
        if known_title:
            found = _search_by_title(known_title)
            candidates += found
            wanted = _norm(known_title)
            matched = [c for c in found if _norm(_title_of(c)) == wanted]
        if not matched and expected_title:
            found = _search_by_title(expected_title)
            candidates += found
            wanted = _norm(expected_title)
            matched = [c for c in found if _norm(_title_of(c)).startswith(wanted)]
        if not attempted:
            if not work:
                search = _get_json(
                    http, f"{OPENALEX_API}/works?search={quote(query)}&per_page=25",
                    result,
                )
                candidates += (search or {}).get("results") or []
            matched = candidates[:1]

    # The identifier the index does not know is named only when nothing was
    # found: alone it says nothing wrong, and it explains a failure.
    unknown = f"has no work under {identifier}, and " if absent else ""

    if not candidates:
        if not result.errors:
            result.errors.append(
                f"the open index has no work under {identifier}, and none by title"
                if absent else "the open index has no such work"
            )
        return result

    if not matched:
        # An unreliable match is worse than no data: one wrong record in the
        # registry destroys trust in all the others.
        if not answered:
            return result  # every search was refused, and each refusal is counted
        titles = ", ".join(repr(title) for title in answered)
        result.errors.append(
            f"the open index {unknown}gave no reliable match by title "
            f"({titles}); no evidence was created"
        )
        return result

    candidates = matched
    best = max(candidates, key=lambda c: c.get("cited_by_count") or 0)
    venue, peer_reviewed = "", False
    for candidate in candidates:
        name, reviewed = _venue_of(candidate)
        if reviewed:
            venue, peer_reviewed = name, True
            break
        venue = venue or name

    cited = best.get("cited_by_count") or 0
    year = best.get("publication_year") or ""
    velocity = _citation_velocity(best, today)

    value = (
        f"venue={venue or 'unknown'}; peer_reviewed={'true' if peer_reviewed else 'false'}; "
        f"cited_by={cited}; year={year}"
    )
    if velocity is not None:
        value += f"; citation_velocity={velocity}"

    # The evidence carries the title the matching ran against rather than the
    # technology's name: the name is shorter than the title of the work, and the
    # later similarity check would reject correct matches. Protection against a
    # foreign work is provided by the strict selection above, which is stricter
    # than a comparison by similarity.
    matched_title = _title_of(best)
    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value=value,
        source=best.get("id") or f"{OPENALEX_API}/works",
        fetched_at=today,
        obtained_by="auto",
        verified=False,
        expected_title=resolved_title or matched_title,
        actual_title=matched_title,
    ))
    return result
