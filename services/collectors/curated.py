"""Discovery from curated topic lists.

The works-and-code catalogue finds new work by task tags, and that is both its
strength and its limit. The tag is applied by whoever uploads the work, so the
catalogue knows exactly what was claimed about a work and does not know whether
the people working in the field have recognised it as theirs. A curated list
knows the opposite: it knows nothing about tags, but inclusion in it is the
decision of a person who understands the subject.

Hence this collector's role. It does not replace the catalogue; it adds a second
selection built on a different principle. A work that made it into a survey list
on graph retrieval has been recognised by the community even when no tag was
ever applied to it.

The collector reads the markup of a list and takes **identifiers** out of it,
while the information about a work comes from the preprint archive. That order
is deliberate: a list is written by hand and its wording cannot be trusted as a
source, whereas an identifier is checkable and unambiguous.

The collector creates no records. It fills the candidate queue, where the
decision is a person's, as it is for every other route of discovery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from services.collectors.arxiv import ARXIV_API, _parse_atom_entries
from services.collectors.base import HttpGetter, is_allowed_host
from services.collectors.paperswithcode import Paper


@dataclass(frozen=True)
class CuratedList:
    """A curated list the identifiers of works are taken from."""

    #: The name of the list. It reaches the candidate queue as the provenance.
    name: str
    #: The address of the markup. The raw file is taken rather than the page:
    #: the page carries the hosting platform's chrome, which changes
    #: independently of the content of the list.
    readme: str
    #: The page of the list, for a reader.
    page: str
    #: The survey the list accompanies, when there is one.
    survey: str | None = None


#: The lists that are polled.
#:
#: The set is deliberately short. A curated list is useful exactly to the extent
#: that a person who understands the subject keeps it; a list assembled for the
#: sake of stars yields noise that has to be sorted out by hand afterwards.
CURATED_LISTS: tuple[CuratedList, ...] = (
    CuratedList(
        name="Awesome-GraphRAG",
        readme="https://raw.githubusercontent.com/DEEP-PolyU/Awesome-GraphRAG/main/README.md",
        page="https://github.com/DEEP-PolyU/Awesome-GraphRAG",
        survey="arXiv:2501.13958",
    ),
)

#: The shape of an entry: the venue in parentheses, the title in bold, and a
#: link to the preprint somewhere after. Exactly this shape is parsed and
#: everything else is passed over: trying to understand arbitrary markup ends in
#: invented titles.
ENTRY = re.compile(
    r"^-\s*\((?P<venue>[^)]{1,60})\)\s*\*\*(?P<title>.+?)\*\*"
    r"(?P<tail>.*?)$",
    re.M,
)

ARXIV_LINK = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>[0-9]{4}\.[0-9]{4,5})")

#: The year inside the venue: "(ICLR 2026)" yields 2026.
VENUE_YEAR = re.compile(r"\b(19|20)(\d{2})\b")

#: How many identifiers are asked for in one request.
#:
#: A limit of politeness rather than of capability: the archive accepts a
#: comma-separated list, and splitting it into separate requests would hammer
#: somebody else's service for nothing.
BATCH = 25


@dataclass(frozen=True)
class ListedEntry:
    """An entry of a list: what the markup yielded, and nothing beyond it."""

    arxiv_id: str
    title: str
    venue: str
    year: int | None


def parse_entries(markup: str) -> list[ListedEntry]:
    """Parse the markup of a list into entries carrying preprint identifiers.

    The function is pure and reaches no network: the parsing is checked against
    recorded markup rather than against whatever sits in somebody else's
    repository today.
    """
    entries: list[ListedEntry] = []
    seen: set[str] = set()
    for match in ENTRY.finditer(markup):
        link = ARXIV_LINK.search(match.group("tail"))
        if not link:
            # An entry without a preprint is passed over in silence: a work may
            # have no identifier at all, and that is not a broken list.
            continue
        arxiv_id = link.group("id")
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        venue = match.group("venue").strip()
        year = VENUE_YEAR.search(venue)
        entries.append(ListedEntry(
            arxiv_id=arxiv_id,
            title=re.sub(r"\s+", " ", match.group("title")).strip(),
            venue=venue,
            year=int(year.group(0)) if year else None,
        ))
    return entries


def _abstracts(
    http: HttpGetter, arxiv_ids: list[str]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Abstracts and dates for a set of identifiers, requested in batches."""
    found: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for start in range(0, len(arxiv_ids), BATCH):
        chunk = arxiv_ids[start:start + BATCH]
        url = f"{ARXIV_API}?id_list={','.join(chunk)}&max_results={len(chunk)}"
        if not is_allowed_host(url):
            problems.append(f"host outside the allowlist: {url}")
            continue
        status, body = http.get(url, timeout=30)
        if status != 200:
            problems.append(f"the archive answered {status} to a batch of {len(chunk)} works")
            continue
        for entry in _parse_atom_entries(body):
            # The identifier in the answer carries a version number; the list
            # does not know it.
            bare = entry["id"].split("v")[0]
            found[bare] = entry
    return found, problems


def discover_from_lists(
    *,
    http: HttpGetter,
    published_after: date | None = None,
    lists: tuple[CuratedList, ...] = CURATED_LISTS,
    known: set[str] | None = None,
) -> tuple[list[Paper], list[str]]:
    """Works from the curated lists, reduced to the common candidate shape.

    `known` holds the identifiers already decided upon or already in the
    registry. Filtering by it happens **before** the archive is asked: a list
    holds a hundred-odd works of which a handful are new, and asking for every
    abstract would hammer somebody else's service to no purpose.
    """
    known = known or set()
    papers: list[Paper] = []
    problems: list[str] = []

    for source in lists:
        if not is_allowed_host(source.readme):
            problems.append(f"host outside the allowlist: {source.readme}")
            continue
        status, body = http.get(source.readme, timeout=30)
        if status != 200:
            problems.append(f"{source.name}: the markup of the list answered {status}")
            continue
        try:
            markup = body.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{source.name}: the markup does not read as UTF-8")
            continue

        entries = parse_entries(markup)
        if not entries:
            # An empty parse of a successful answer means the list has changed
            # the shape of its entries. Silence is not an option here: the
            # collector would look as though it were working.
            problems.append(
                f"{source.name}: the markup arrived and not one entry parsed; "
                "the shape of the list has probably changed"
            )
            continue

        fresh = [entry for entry in entries if entry.arxiv_id not in known]
        if published_after is not None:
            fresh = [
                entry for entry in fresh
                if entry.year is None or entry.year >= published_after.year
            ]
        if not fresh:
            continue

        details, trouble = _abstracts(http, [entry.arxiv_id for entry in fresh])
        problems.extend(f"{source.name}: {item}" for item in trouble)

        for entry in fresh:
            detail = details.get(entry.arxiv_id)
            if not detail:
                # No abstract, no candidate. Judging fitness from a title alone
                # would mean passing a guess off as a measurement.
                problems.append(
                    f"{source.name}: the archive did not return {entry.arxiv_id}"
                )
                continue
            published = detail.get("published") or ""
            papers.append(Paper(
                arxiv_id=entry.arxiv_id,
                # The title comes from the archive rather than from the list:
                # a list is written by hand, and a typo in it would spread
                # through the candidate queue.
                title=detail.get("title") or entry.title,
                abstract=detail.get("summary", ""),
                published=date.fromisoformat(published) if len(published) == 10 else None,
                venue=entry.venue,
                citations=None,
                url=f"https://arxiv.org/abs/{entry.arxiv_id}",
                repositories=[],
                tasks=[],
            ))
    return papers, problems
