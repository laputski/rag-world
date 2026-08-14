"""The preprint-archive collector.

Asks the archive about a publication by its identifier, extracts the metadata
and returns candidate evidence of the publication type. Writing to the registry
is the orchestrator's job.

The interface answers Atom XML at
http://export.arxiv.org/api/query?id_list=XXXX.XXXXX, with the title inside
<entry><title>.

The title matters beyond display: the cross-check stage compares the title the
archive returns against the title the registry expects. That comparison is what
found three links pointing at a different work than the record claimed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

from services.collectors.base import CollectResult, HttpGetter, RawEvidence, is_allowed_host

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _extract_arxiv_id(url: str) -> str | None:
    """Pull the archive identifier out of a URL, or return an identifier as is."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/[0-9]{7})", url, re.I)
    if m:
        return m.group(1)
    # A bare identifier.
    if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}|[a-z\-]+/[0-9]{7}", url):
        return url
    return None


def _parse_atom_entries(xml_bytes: bytes) -> list[dict[str, str]]:
    """Extract the entries of an Atom answer: [{id, title, published, summary}]."""
    entries: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return entries
    for entry in root.findall(f"{ATOM_NS}entry"):
        arxiv_id = ""
        id_text = entry.findtext(f"{ATOM_NS}id", default="") or ""
        m = re.search(r"arxiv\.org/abs/([^/\s]+)", id_text)
        if m:
            arxiv_id = m.group(1)
        title = (entry.findtext(f"{ATOM_NS}title", default="") or "").strip()
        title = re.sub(r"\s+", " ", title)
        published = entry.findtext(f"{ATOM_NS}published", default="") or ""
        # The abstract was promised by this function's description from the
        # start yet was not extracted. Discovery from curated lists judges a
        # work's fitness by the abstract, and without it the judgement degrades
        # into a guess from the title.
        summary = (entry.findtext(f"{ATOM_NS}summary", default="") or "").strip()
        summary = re.sub(r"\s+", " ", summary)
        entries.append({
            "id": arxiv_id, "title": title,
            "published": published[:10], "summary": summary,
        })
    return entries


def collect_arxiv(
    technology_id: str,
    arxiv_id_or_url: str,
    *,
    http: HttpGetter,
    expected_title: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Collect a publication from the preprint archive by identifier or URL.

    Returns one piece of raw evidence of the publication type, carrying the
    title the archive actually returned. When `expected_title` is given, the
    cross-check stage compares the two.
    """
    today = today or date.today()
    result = CollectResult(source_name="arxiv", technology_id=technology_id)

    arxiv_id = _extract_arxiv_id(arxiv_id_or_url)
    if not arxiv_id:
        result.errors.append(f"no archive identifier could be read from {arxiv_id_or_url!r}")
        return result

    url = f"{ARXIV_API}?id_list={arxiv_id}"
    if not is_allowed_host(url):
        result.skipped.append(f"host outside the allowlist: {url}")
        return result

    status, body = http.get(url, timeout=20)
    if status != 200:
        result.errors.append(f"the preprint archive answered {status} for {arxiv_id}")
        return result

    entries = _parse_atom_entries(body)
    if not entries:
        result.errors.append(f"the preprint archive has no entry for {arxiv_id}")
        return result

    entry = entries[0]
    actual_title = entry["title"]
    # The year of publication, which the cross-check stage tests for plausibility.
    year = entry["published"][:4] if entry["published"] else ""

    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value=f"arXiv:{arxiv_id} ({year})",
        source=f"https://arxiv.org/abs/{arxiv_id}",
        fetched_at=today,
        obtained_by="auto",
        verified=False,  # the cross-check stage decides whether it is verified
        expected_title=expected_title,
        actual_title=actual_title,
    ))
    return result
