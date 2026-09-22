"""Discovery from the preprint archive: the third route.

The two routes that came before it both ask somebody else what belongs to the
subject. The works-and-code catalogue asks a tag, applied by whoever uploaded
the work. A curated list asks a person who keeps the list. Both are useful and
both are narrow in the same direction: a work reaches them only if somebody
else has already decided it belongs.

That narrowness has a measured cost. MAGMA, a memory architecture published at
the main conference of ACL and entered in this registry by hand, was found by
neither: the catalogue's method tag was never applied to it and no list on graph
retrieval holds it. The record came in from outside the queue, which is the one
thing the queue exists to prevent.

This route asks the archive itself, by category and by the phrases that name the
subject, and so does not depend on anyone having classified the work first.

Two decisions shape it, and both were taken from measurement rather than taste.

**Only works that name themselves.** In one week the phrases below matched forty
works in the three categories, of which nineteen carry a name before the colon
in the title and twenty-one do not. The twenty-one are studies and applications
("A Controlled Study of Model Scale for Ontology Learning", "Towards a Joint
Khmer Text Recognition"), which is the class the queue refuses by hand again and
again. The registry holds named retrieval technologies, so the route looks for
named work; a rule that reads the shape of a title asserts nothing about the
quality of what it drops.

**No silent truncation.** The archive answers at most as many works as it is
asked for. When the answer fills the cap, the route says so rather than passing
a truncated week off as a whole one.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from urllib.parse import quote

from services.collectors.arxiv import ARXIV_API, _parse_atom_entries
from services.collectors.base import HttpGetter, is_allowed_host
from services.collectors.paperswithcode import Paper

#: The categories asked. Retrieval work sits in information retrieval, in
#: computation and language, and in artificial intelligence; a fourth category
#: would widen the answer without widening the subject.
CATEGORIES: tuple[str, ...] = ("cs.IR", "cs.CL", "cs.AI")

#: The phrases that name the subject in an abstract. Each was measured: in one
#: week the first matched thirty-five works, agentic memory four, graph
#: retrieval four, memory-augmented generation none. The list is short on
#: purpose: a phrase that matches the field at large returns the field at large.
PHRASES: tuple[str, ...] = (
    "retrieval-augmented generation",
    "agentic memory",
    "memory-augmented generation",
    "graph retrieval",
)

#: How many works are asked for at once. The archive is asked for the newest
#: first, so the cap bites only when a week brought more than this.
MAX_RESULTS = 200

#: A title of the form "MAGMA: A Multi-Graph based Agentic Memory Architecture":
#: the name stands before the colon and is short. The pattern is the one the
#: fitness rule already uses, and it is imported rather than repeated so that
#: the two cannot drift apart.
from core.candidate_fit import _NAMED  # noqa: E402


def build_query(
    categories: tuple[str, ...] = CATEGORIES,
    phrases: tuple[str, ...] = PHRASES,
) -> str:
    """The search expression the archive is asked with.

    The phrases are searched in the abstract rather than in the whole record: a
    full-text match returns every work that mentions retrieval in passing.
    """
    cats = " OR ".join(f"cat:{c}" for c in categories)
    terms = " OR ".join(f'abs:"{p}"' for p in phrases)
    return f"({cats}) AND ({terms})"


def discover_from_archive(
    *,
    http: HttpGetter,
    published_after: date,
    categories: tuple[str, ...] = CATEGORIES,
    phrases: tuple[str, ...] = PHRASES,
    max_results: int = MAX_RESULTS,
) -> tuple[list[Paper], list[str], list[str]]:
    """Named work from the archive, published no earlier than the given date.

    Returns three things, as the catalogue route does: what was found, refusals,
    and what a check dropped. A work outside the window or without a name in its
    title is a discard, not a refusal: the archive answered.
    """
    query = build_query(categories, phrases)
    url = (
        f"{ARXIV_API}?search_query={quote(query)}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )
    if not is_allowed_host(url):
        return [], [f"host outside the allowlist: {url}"], []

    status, body = http.get(url, timeout=40)
    if status != 200:
        return [], [f"the preprint archive answered {status} to the feed request"], []

    # An answer that is not a feed at all is a refusal. It used to be filed
    # among the discards, where the pass prints only the first discard, and
    # that one is always the catalogue's weekly note about dates: an archive
    # answering with a page of HTML every week would have looked like a quiet
    # archive for as long as it lasted.
    try:
        ET.fromstring(body)
    except ET.ParseError:
        return [], [
            "the preprint archive answered the feed request with something "
            "that is not a feed"
        ], []

    entries = _parse_atom_entries(body)
    if not entries:
        # A feed without entries is an answer: a week without matching work can
        # happen. The caller is told, and decides nothing on silence.
        return [], [], ["the archive returned no entries for the feed request"]

    papers: list[Paper] = []
    discarded: list[str] = []
    problems: list[str] = []
    reached_the_edge = False
    for entry in entries:
        arxiv_id = (entry.get("id") or "").split("v")[0]
        title = entry.get("title") or ""
        published = entry.get("published") or ""
        when = date.fromisoformat(published) if len(published) == 10 else None
        if not arxiv_id or when is None:
            discarded.append(f"an entry without an identifier or a date: {title[:60]!r}")
            continue
        if when < published_after:
            # The archive answers newest first, so everything after the first
            # such work is older still; the loop is left rather than continued.
            # Reaching this point means the window was covered to its far edge.
            reached_the_edge = True
            break
        if not _NAMED.match(title):
            discarded.append(f"the work does not name itself in its title: {title[:70]!r}")
            continue
        papers.append(Paper(
            arxiv_id=arxiv_id,
            title=re.sub(r"\s+", " ", title).strip(),
            abstract=entry.get("summary", ""),
            published=when,
            venue=None,
            citations=None,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            repositories=[],
            tasks=[],
        ))

    if not reached_the_edge and len(entries) >= max_results:
        # The answer filled the cap and never reached the far edge of the
        # window, so works inside the window are missing from it. Both halves of
        # the condition matter: the archive always has more matching work than
        # the cap, and reporting on the cap alone would raise the alarm on every
        # pass and so raise it on none.
        problems.append(
            f"the feed filled the limit of {max_results} works without reaching "
            f"{published_after.isoformat()}, so the oldest work of the window is missing"
        )
    return papers, problems, discarded
