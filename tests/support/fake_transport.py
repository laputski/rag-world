"""The fake transport: running the chain without a network.

All the coverage of the weekly pass rests on this. While the chain reaches the
network there is nothing to check: the result depends on what the preprint
archive returns today, and the unhealthy cases — a refusal, a rate limit, a
corrupted answer — cannot be reproduced at all.

The transport returns recorded answers by a substring of the address and knows
how to behave badly: refuse, stay silent, return rubbish. It counts the requests,
so it can be checked both that a source was polled and that no superfluous
requests were made.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sources"


def load_fixture(name: str) -> bytes:
    """A recorded answer from a source."""
    return (FIXTURES / name).read_bytes()


@dataclass
class SourceBehaviour:
    """How a source answers: the body, the status and how often it refuses first.

    `fail_times` describes a source that refuses on rate for a while and then
    returns the data — without it there is no way to test the retry with a pause.
    """

    body: bytes = b""
    status: int = 200
    fail_times: int = 0
    fail_status: int = 429


@dataclass
class FakeTransport:
    """Returns prepared answers by a substring of the address.

    An address matching no rule receives a 404: silence about a source nobody
    expected is better than an invented answer.
    """

    routes: dict[str, SourceBehaviour] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    _failures: dict[str, int] = field(default_factory=dict)

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        self.calls.append(url)
        for marker, behaviour in self.routes.items():
            if marker in url:
                seen = self._failures.get(marker, 0)
                if seen < behaviour.fail_times:
                    self._failures[marker] = seen + 1
                    return (behaviour.fail_status, b"")
                return (behaviour.status, behaviour.body)
        return (404, b"{}")

    def calls_matching(self, marker: str) -> list[str]:
        return [c for c in self.calls if marker in c]


def standard_routes() -> dict[str, SourceBehaviour]:
    """Healthy answers from every source: the baseline tests depart from."""
    return {
        "export.arxiv.org": SourceBehaviour(load_fixture("arxiv_entry.xml")),
        "api.openalex.org/works/doi": SourceBehaviour(
            load_fixture("openalex_preprint.json")
        ),
        "api.openalex.org/works?filter=title.search": SourceBehaviour(
            load_fixture("openalex_search.json")
        ),
        "api.github.com/repos/demo/demo/releases": SourceBehaviour(b"[]"),
        "api.github.com/repos/demo/demo": SourceBehaviour(
            load_fixture("github_repo.json")
        ),
        # The directory listings of the framework integration folders.
        "contents": SourceBehaviour(load_fixture("github_contents.json")),
        "pypi.org/pypi": SourceBehaviour(load_fixture("pypi_meta.json")),
        "pypistats.org": SourceBehaviour(load_fixture("pypistats.json")),
    }


def route_without(routes: dict[str, SourceBehaviour], marker: str) -> dict:
    """The same rules without one source, which will then refuse."""
    return {k: v for k, v in routes.items() if k != marker}


def json_body(payload: object) -> bytes:
    return json.dumps(payload).encode()
