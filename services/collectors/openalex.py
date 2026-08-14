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

#: The open index keeps two request pools, a common one and a polite one. Limits
#: in the second are noticeably higher, and a contact address is what admits a
#: caller to it, by their own design. Without it the run hits a refusal on rate
#: and half the records are left without their publication venue.
#:
#: The address comes from the environment rather than being written into the
#: code: the repository is read by strangers, and a personal address is not
#: something to publish in it.
OPENALEX_MAILTO_ENV = "OPENALEX_MAILTO"


def _polite(url: str) -> str:
    """Append the contact address to the URL when the environment supplies one."""
    import os

    mailto = os.environ.get(OPENALEX_MAILTO_ENV, "").strip()
    if not mailto:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}mailto={quote(mailto)}"

_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5})", re.I)
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


def _get_json(http: HttpGetter, url: str, result: CollectResult) -> dict | None:
    if not is_allowed_host(url):
        result.skipped.append(f"host outside the allowlist: {url}")
        return None
    status, body = http.get(
        url, headers={"User-Agent": "rag-world/0.2 (registry collector)"}, timeout=20
    )
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
        venue = DOI_PREFIX_VENUES.get(prefix) or best_name or f"DOI {prefix}"
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
    today: date | None = None,
) -> CollectResult:
    """Collect the venue, whether it was reviewed, and the citations.

    `query` is a preprint address, an identifier or the title of a work. The
    result is evidence of the publication type; the citation figures go into the
    value field, from which the orchestrator takes them for the time series.
    """
    today = today or date.today()
    result = CollectResult(source_name="openalex", technology_id=technology_id)

    work: dict | None = None

    arxiv_match = _ARXIV_RE.search(query)
    doi_match = _DOI_RE.search(query)
    if arxiv_match:
        # A preprint has a canonical identifier, which is the most reliable key.
        doi = f"10.48550/arXiv.{arxiv_match.group('id')}"
        work = _get_json(http, _polite(f"{OPENALEX_API}/works/doi:{doi}"), result)
    elif doi_match:
        work = _get_json(http, _polite(f"{OPENALEX_API}/works/doi:{doi_match.group(0)}"), result)

    def _norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _title_of(candidate: dict) -> str:
        return (candidate.get("title") or candidate.get("display_name") or "").strip()

    # The title the other versions of the work are searched by. A title resolved
    # from an identifier carries more authority than the technology's name: the
    # latter can coincide with an unrelated work.
    resolved_title = _title_of(work) if work else ""
    search_title = resolved_title or (expected_title or "")

    # The second step: the preprint and the conference publication are separate
    # records, and peer review is visible only on the second.
    candidates: list[dict] = [work] if work else []
    if search_title:
        # Inside a filter the comma and the vertical bar separate conditions,
        # the colon separates a filter name from its value, and the question
        # mark and the asterisk stand for wildcards. Titles of works contain
        # them constantly: "What Retrieval Granularity Should We Use?" broke the
        # request with a 400, and the work silently stayed without a venue.
        #
        # The separators are replaced by a space. Word search does not suffer
        # from that, and the request stops being inadmissible.
        safe_title = re.sub(r"[,|:?*]+", " ", search_title).strip()
        search = _get_json(
            http,
            _polite(f"{OPENALEX_API}/works?filter=title.search:{quote(safe_title)}&per_page=25"),
            result,
        )
        if search:
            candidates.extend(search.get("results") or [])
    elif not work:
        search = _get_json(
            http, _polite(f"{OPENALEX_API}/works?search={quote(query)}&per_page=25"), result
        )
        if search:
            candidates.extend(search.get("results") or [])

    if not candidates:
        if not result.errors:
            result.errors.append("the open index has no such work")
        return result

    # Selecting the matches. When the work was resolved by identifier, only
    # records with the same title are accepted. When it was not, the technology's
    # name must begin the title of the work: "Self-RAG" fits "Self-RAG: Learning
    # to Retrieve...", and does not fit an unrelated work that merely mentions
    # it.
    if resolved_title:
        wanted = _norm(resolved_title)
        matched = [c for c in candidates if _norm(_title_of(c)) == wanted]
    elif expected_title:
        wanted = _norm(expected_title)
        matched = [c for c in candidates if _norm(_title_of(c)).startswith(wanted)]
    else:
        matched = candidates[:1]

    if not matched:
        # An unreliable match is worse than no data: one wrong record in the
        # registry destroys trust in all the others.
        result.errors.append(
            f"the open index gave no reliable match by title "
            f"({search_title!r}); no evidence was created"
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
