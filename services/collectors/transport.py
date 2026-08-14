"""The HTTP transport the collectors run on.

A wrapper over the HTTP library implementing the interface collectors expect.
Tests replace it with a stub, which is why they need no network.

The transport keeps two rules, and without them an unattended run would soon be
refused by the sources:

* **the allowlist of hosts** — a request to a host outside it is not made at
  all, even when a collector asks for one by mistake;
* **a polite rate** — a pause is held between requests to the same host. The
  preprint archive asks for no more than one request every three seconds and
  refuses when that is broken; the open indexes are more tolerant, but they too
  should not be sent requests without pauses.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

from services.collectors.base import is_allowed_host

#: The least pause between two requests to the same host, in seconds.
HOST_DELAYS: dict[str, float] = {
    "export.arxiv.org": 4.0,
    "arxiv.org": 4.0,
    # Five requests a second is more than the open index bears: it refuses on
    # rate even with retries. One second passes in the common request pool. A
    # contact address would buy a higher limit, but supplying one is optional
    # and the run has to work without it.
    "api.openalex.org": 1.0,
    "api.github.com": 1.0,
    "pypi.org": 0.2,
    "paperswithcode.co": 1.0,
}
DEFAULT_DELAY = 0.5

#: How many times a request is repeated after a refusal on rate.
RETRIES_ON_RATE_LIMIT = 3

#: How a request introduces itself to the host.
#:
#: Many hosts refuse an unintroduced request as robotic, and that refusal is
#: indistinguishable from "the page is closed". It happened once already: a
#: reference article answered with a refusal, and only once the request
#: introduced itself did it become visible that the article does not exist at
#: all. Saying nothing about yourself does not make a request politer, it makes
#: the answer less truthful.
DEFAULT_USER_AGENT = "rag-world/0.2 (registry; +https://ragworld.org)"


class RequestsTransport:
    """An HTTP transport that holds a polite rate.

    `allow_any_host` lifts the allowlist and exists for exactly one task:
    checking that the registry's own links resolve. The allowlist is there so
    that evidence collection does not follow addresses met in the content of a
    source. The registry's links are the opposite case — they were written by
    us, and half of them lead to venues that are not on the list and should not
    be.
    """

    def __init__(self, allow_any_host: bool = False) -> None:
        self._last_call: dict[str, float] = {}
        self._allow_any_host = allow_any_host

    def _wait(self, host: str) -> None:
        delay = HOST_DELAYS.get(host, DEFAULT_DELAY)
        previous = self._last_call.get(host)
        if previous is not None:
            elapsed = time.monotonic() - previous
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self._last_call[host] = time.monotonic()

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        # The allowlist is checked twice over: collectors check it themselves,
        # and the transport must not reach a foreign address even when one of
        # them is wrong.
        if not self._allow_any_host and not is_allowed_host(url):
            return (403, b"host not in allowlist")

        host = (urlparse(url).hostname or "").lower()
        for attempt in range(RETRIES_ON_RATE_LIMIT + 1):
            self._wait(host)
            try:
                # The introduction is supplied when the caller gave none: one
                # place instead of a repetition in every collector.
                sent = {"User-Agent": DEFAULT_USER_AGENT, **(headers or {})}
                resp = requests.get(url, headers=sent, timeout=timeout)
            except requests.RequestException as exc:
                return (0, str(exc).encode())
            if resp.status_code != 429 or attempt == RETRIES_ON_RATE_LIMIT:
                return (resp.status_code, resp.content)
            # Refused on rate: wait longer than usual and try once more.
            time.sleep(HOST_DELAYS.get(host, DEFAULT_DELAY) * (attempt + 2))
        return (429, b"rate limited")
