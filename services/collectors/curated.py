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
    # The list kept alongside the survey of graph retrieval. It reached the
    # registry the other way round: the survey itself was refused as a record,
    # because a survey is not a point in the configuration space, and the note
    # of the refusal said it would serve as a source of discovery instead. It
    # could not until the parser learned the shape its entries are written in.
    CuratedList(
        name="Graph-RAG survey list",
        readme="https://raw.githubusercontent.com/Graph-RAG/GraphRAG/main/README.md",
        page="https://github.com/Graph-RAG/GraphRAG",
        survey="arXiv:2501.00309",
    ),
)

#: The shapes of an entry: the venue, the title in bold, and a link to the
#: preprint somewhere after. Exactly these shapes are parsed and everything else
#: is passed over: trying to understand arbitrary markup ends in invented titles.
#:
#: There are two of them because lists in this field write the venue in two
#: ways, in parentheses and in square brackets, and a list written the second
#: way parsed to nothing at all. That is not a hypothetical: the survey list of
#: graph retrieval gave zero entries out of two hundred and one, and the
#: collector reported it as a list whose shape had changed rather than as a list
#: it could not read.
ENTRY_PATTERNS = (
    re.compile(
        r"^\s*-\s*\((?P<venue>[^)]{1,60})\)\s*\*\*(?P<title>.+?)\*\*"
        r"(?P<tail>.*?)$",
        re.M,
    ),
    re.compile(
        r"^\s*-\s*\[(?P<venue>[^\]]{1,60})\]\s*\*\*(?P<title>.+?)\*\*"
        r"(?P<tail>.*?)$",
        re.M,
    ),
)

ARXIV_LINK = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>[0-9]{4}\.[0-9]{4,5})")

#: The year inside the venue: "(ICLR 2026)" yields 2026, and "[NeurIPS 24]"
#: yields 2024. The short form is read because lists that write the venue in
#: square brackets write the year in two digits, and without it every entry of
#: such a list looked undated and was sent to the archive to be asked about.
VENUE_YEAR = re.compile(r"\b(19|20)(\d{2})\b")
#: A two-digit year is only read inside a range that this field's work falls in:
#: a bare number outside it is more likely part of a venue's name than a year.
SHORT_YEAR = re.compile(r"\b(\d{2})\b")
SHORT_YEAR_RANGE = range(15, 36)


def _venue_year(venue: str) -> int | None:
    """The year of publication as the venue tag of a list gives it."""
    full = VENUE_YEAR.search(venue)
    if full:
        return int(full.group(0))
    short = SHORT_YEAR.search(venue)
    if short and int(short.group(1)) in SHORT_YEAR_RANGE:
        return 2000 + int(short.group(1))
    return None

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
    matches = [m for pattern in ENTRY_PATTERNS for m in pattern.finditer(markup)]
    for match in matches:
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
        entries.append(ListedEntry(
            arxiv_id=arxiv_id,
            title=re.sub(r"\s+", " ", match.group("title")).strip(),
            venue=venue,
            year=_venue_year(venue),
        ))
    return entries


def _abstracts(
    http: HttpGetter, arxiv_ids: list[str]
) -> tuple[dict[str, dict[str, str]], list[str], set[str]]:
    """Abstracts and dates for a set of identifiers, requested in batches.

    The third value holds the identifiers of the batches that were refused. A
    work in such a batch is not missing from the archive; nobody was told about
    it, and the refusal of its batch already says so once.
    """
    found: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    unasked: set[str] = set()
    for start in range(0, len(arxiv_ids), BATCH):
        chunk = arxiv_ids[start:start + BATCH]
        url = f"{ARXIV_API}?id_list={','.join(chunk)}&max_results={len(chunk)}"
        if not is_allowed_host(url):
            problems.append(f"host outside the allowlist: {url}")
            unasked.update(chunk)
            continue
        status, body = http.get(url, timeout=30)
        if status != 200:
            problems.append(f"the archive answered {status} to a batch of {len(chunk)} works")
            unasked.update(chunk)
            continue
        for entry in _parse_atom_entries(body):
            # The identifier in the answer carries a version number; the list
            # does not know it.
            bare = entry["id"].split("v")[0]
            found[bare] = entry
    return found, problems, unasked


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
    # The works already taken from an earlier list. A work held by two lists is
    # fetched once and credited to both: asking again doubled the requests and
    # put the work into the queue twice in one pass.
    taken: dict[str, Paper] = {}

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

        for entry in entries:
            if entry.arxiv_id in taken and source.name not in taken[entry.arxiv_id].curated_by:
                taken[entry.arxiv_id].curated_by.append(source.name)
        fresh = [
            entry for entry in entries
            if entry.arxiv_id not in known and entry.arxiv_id not in taken
        ]
        if published_after is not None:
            fresh = [
                entry for entry in fresh
                if entry.year is None or entry.year >= published_after.year
            ]
        if not fresh:
            continue

        details, trouble, unasked = _abstracts(http, [entry.arxiv_id for entry in fresh])
        problems.extend(f"{source.name}: {item}" for item in trouble)

        for entry in fresh:
            detail = details.get(entry.arxiv_id)
            if not detail and entry.arxiv_id in unasked:
                continue
            if not detail:
                # No abstract, no candidate. Judging fitness from a title alone
                # would mean passing a guess off as a measurement.
                problems.append(
                    f"{source.name}: the archive did not return {entry.arxiv_id}"
                )
                continue
            published = detail.get("published") or ""
            when = date.fromisoformat(published) if len(published) == 10 else None
            # The window the caller asked for, applied to the date the archive
            # gives rather than to the year the list writes. The list knows only
            # a year, so the filter above admits the whole of it; here the real
            # date is known, and a work from the January before the window is
            # outside it. Without this the queue took in two years and a half
            # where two were asked for, and a single list emptied a season of
            # triage into it.
            if published_after is not None and when is not None and when < published_after:
                continue
            paper = Paper(
                arxiv_id=entry.arxiv_id,
                # The title comes from the archive rather than from the list:
                # a list is written by hand, and a typo in it would spread
                # through the candidate queue.
                title=detail.get("title") or entry.title,
                abstract=detail.get("summary", ""),
                published=when,
                venue=entry.venue,
                citations=None,
                url=f"https://arxiv.org/abs/{entry.arxiv_id}",
                repositories=[],
                tasks=[],
                curated_by=[source.name],
            )
            taken[entry.arxiv_id] = paper
            papers.append(paper)
    return papers, problems
