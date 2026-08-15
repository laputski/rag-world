"""How the transport behaves under refusals and rate limits.

Politeness towards the sources is not decoration: the preprint archive refuses
requests that come too often, and an unattended pass that cannot wait quietly
loses data every week. A refusal on rate differs from any other in being
temporary, so it is handled differently — by a retry with a growing pause.

Sleep and the network itself are substituted: the test must neither wait nor
reach out.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.collectors import transport as tr  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"{}") -> None:
        self.status_code = status_code
        self.content = content


@pytest.fixture
def no_sleep(monkeypatch):
    """The pauses are recorded rather than held."""
    slept: list[float] = []
    monkeypatch.setattr(tr.time, "sleep", slept.append)
    return slept


@pytest.fixture
def responses(monkeypatch):
    """A queue of network answers; the actual requests are recorded."""
    queue: list[FakeResponse] = []
    calls: list[str] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return queue.pop(0) if queue else FakeResponse(200)

    monkeypatch.setattr(tr.requests, "get", fake_get)
    return queue, calls


URL = "https://api.openalex.org/works/W1"


def test_rate_limit_is_retried_until_success(no_sleep, responses):
    """A refusal on rate is temporary, so the request is repeated."""
    queue, calls = responses
    queue.extend([
        FakeResponse(429), FakeResponse(429), FakeResponse(200, b'{"ok": true}')
    ])

    status, body = tr.RequestsTransport().get(URL)

    assert status == 200
    assert body == b'{"ok": true}'
    assert len(calls) == 3, "two refusals mean two retries"


def test_pause_grows_between_retries(no_sleep, responses, monkeypatch):
    """The pause grows: a retry at the same rate hits the same limit again.

    The politeness pause is disabled here, or it mixes with the backoff and the
    record becomes unreadable.
    """
    monkeypatch.setattr(tr.RequestsTransport, "_wait", lambda self, host: None)
    queue, _ = responses
    queue.extend([FakeResponse(429), FakeResponse(429), FakeResponse(200)])

    tr.RequestsTransport().get(URL)

    assert len(no_sleep) == 2, f"two backoff pauses were expected: {no_sleep}"
    assert no_sleep[1] > no_sleep[0], f"the pauses do not grow: {no_sleep}"


def test_retries_are_bounded(no_sleep, responses):
    """A source that always refuses must not hold the pass for ever."""
    queue, calls = responses
    queue.extend([FakeResponse(429)] * 50)

    status, _ = tr.RequestsTransport().get(URL)

    assert status == 429, "out of retries the transport returns the refusal, not data"
    assert len(calls) == tr.RETRIES_ON_RATE_LIMIT + 1


def test_other_failures_are_not_retried(no_sleep, responses):
    """A missing page will not appear on a retry: retrying here is waste."""
    queue, calls = responses
    queue.extend([FakeResponse(404), FakeResponse(200)])

    status, _ = tr.RequestsTransport().get(URL)

    assert status == 404
    assert len(calls) == 1


def test_network_error_is_reported_not_raised(no_sleep, monkeypatch):
    """A broken network is one source refusing, not the whole pass failing."""
    def boom(url, headers=None, timeout=None):
        raise tr.requests.RequestException("the network is unreachable")

    monkeypatch.setattr(tr.requests, "get", boom)
    status, body = tr.RequestsTransport().get(URL)

    assert status == 0
    assert b"\xd1\x81\xd0\xb5\xd1\x82\xd1\x8c" in body or body


def test_foreign_host_is_never_contacted(no_sleep, responses):
    """The allowlist is checked before the request rather than after."""
    _, calls = responses

    status, _ = tr.RequestsTransport().get("https://example.invalid/steal")

    assert status == 403
    assert calls == [], "no request was made to the foreign address"


def test_polite_delay_is_kept_between_calls(no_sleep, responses):
    """A pause is held between two requests to the same host."""
    http = tr.RequestsTransport()
    http.get("https://export.arxiv.org/api/query?id_list=1")
    http.get("https://export.arxiv.org/api/query?id_list=2")

    assert any(w > 0 for w in no_sleep), "the second request went out with no pause"


def test_request_identifies_itself(no_sleep, monkeypatch):
    """Many venues refuse an unintroduced request as robotic.

    That refusal is indistinguishable from "the page is closed", and the link check
    once reported a page that does not exist as sound.
    """
    seen: list[dict] = []

    def fake_get(url, headers=None, timeout=None):
        seen.append(headers or {})
        return FakeResponse(200)

    monkeypatch.setattr(tr.requests, "get", fake_get)
    tr.RequestsTransport().get(URL)

    assert "User-Agent" in seen[0]
    assert "rag-world" in seen[0]["User-Agent"]


def test_caller_headers_win_over_the_default(no_sleep, monkeypatch):
    """A collector that needs its own introduction must not lose it."""
    seen: list[dict] = []

    def fake_get(url, headers=None, timeout=None):
        seen.append(headers or {})
        return FakeResponse(200)

    monkeypatch.setattr(tr.requests, "get", fake_get)
    tr.RequestsTransport().get(
        URL, headers={"User-Agent": "custom", "Accept": "application/json"}
    )

    assert seen[0]["User-Agent"] == "custom"
    assert seen[0]["Accept"] == "application/json"
