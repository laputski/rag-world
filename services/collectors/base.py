"""The models every evidence collector shares.

Collectors poll sources — the preprint archive, the open index of works, code
hosting — and return raw candidate evidence in one neutral format. Writing to
the registry is the orchestrator's job, not the collector's, which is what makes
a collector testable without a store and with the HTTP client replaced.

The invariants:

  - collection happens only against an allowlist of hosts;
  - evidence is never overwritten, only appended;
  - every piece of evidence carries a type, a resolvable source and the date it
    was fetched;
  - the cross-check stage decides deterministically, with no language model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

# ─── The allowlist of hosts ──────────────────────────────────────────────────
# Collecting from a host outside this list requires a deliberate addition here.
# The list grows as collectors are written, not in anticipation of them.

ALLOWED_HOSTS: frozenset[str] = frozenset({
    "arxiv.org",
    "export.arxiv.org",
    "api.openalex.org",
    # A work's identifier in the open index has the form openalex.org/W..., and
    # that is what ends up in the source field of the evidence.
    "openalex.org",
    "api.github.com",
    "github.com",
    # Curated lists are read as the raw file rather than as the page: the page
    # carries the hosting platform's chrome, which changes independently of the
    # list.
    "raw.githubusercontent.com",
    "pypi.org",
    # The package index does not publish download counts; a separate service
    # does.
    "pypistats.org",
    "aclanthology.org",
    "doi.org",
    # The catalogue of works and their code that the community has kept since
    # paperswithcode.com closed. It gives the publication venue from a second
    # source, and a feed of works under a method tag for discovering new ones.
    "paperswithcode.co",
    # Venues that evidence entered by a person points to: some peer-reviewed
    # publications exist nowhere else.
    "openreview.net",
    "dl.acm.org",
    "proceedings.neurips.cc",
    "openaccess.thecvf.com",
    "www.nature.com",
    "nature.com",
    "www.anthropic.com",
    "anthropic.com",
})


def is_allowed_host(url: str) -> bool:
    """True when the URL's host is on the allowlist."""
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    host = host.lower()
    if host in ALLOWED_HOSTS:
        return True
    # Subdomains of an allowed host count as allowed.
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


# ─── The HTTP client, injected so that tests need no network ─────────────────


class HttpGetter(Protocol):
    """The smallest HTTP interface a collector needs.

    Returns (status, body) for a URL and headers. In a real run it wraps the
    HTTP library; in a test it replays a recorded response.
    """

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        ...


# ─── Raw candidate evidence ──────────────────────────────────────────────────


@dataclass
class RawEvidence:
    """A candidate piece of evidence as a collector extracted it.

    It does not reach the registry directly: it is normalised, checked for
    belonging to the record it claims, cross-checked against a second source,
    and only then written. What is defined here is the neutral format all
    collectors share.
    """

    technology_id: str                # the record this is about
    type: str                         # publication, repository, and so on
    value: str                        # the content: venue, identifier, licence
    source: str                       # a resolvable URL
    fetched_at: date                  # the date it was fetched
    obtained_by: str = "auto"         # auto or manual
    # Fields the deterministic cross-checks need.
    verified: bool = False
    # The titles compared to catch a source that describes a different work.
    expected_title: str | None = None
    actual_title: str | None = None


@dataclass
class CollectResult:
    """What one source yielded for one record."""

    source_name: str                  # 'arxiv' | 'openalex' | 'github'
    technology_id: str
    evidence: list[RawEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # What was found but not taken, a host outside the allowlist for instance.
    skipped: list[str] = field(default_factory=list)
