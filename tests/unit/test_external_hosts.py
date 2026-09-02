"""The rule about outside hosts, and the ways it could be walked around.

The rule is applied to the deployed portal by a smoke check that is kept out of
the ordinary suite: it needs a network, and a test that fails on somebody else's
network stops being read. That is exactly why the deciding is exercised here. A
rule that runs only where nobody watches is a rule that quietly stops holding,
and this one already spent seventeen days contradicting the deployed page before
anybody ran it.

One exception was granted, to the visit counter, and the decoys below are mostly
about what the exception must not become: a door held open for anything that
looks a little like it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.support.external_hosts import (  # noqa: E402
    ALLOWED_HOSTS,
    COUNTER_HOST,
    PORTAL_HOST,
    stray_hosts,
)


def page(*addresses: str) -> str:
    body = "".join(f'<script src="{a}"></script>' for a in addresses)
    return f"<html><head>{body}</head><body></body></html>"


# ─── What the rule permits ───────────────────────────────────────────────────


def test_the_portal_may_name_itself():
    assert stray_hosts(page(f"https://{PORTAL_HOST}/assets/index.js")) == []


def test_the_counter_is_permitted():
    """The exception, and the whole reason this file exists."""
    assert stray_hosts(page(f"https://{COUNTER_HOST}/metrika/tag.js?id=1")) == []


def test_a_relative_address_is_not_an_outside_host():
    assert stray_hosts('<link href="/assets/style.css" />') == []


def test_the_host_is_compared_without_regard_to_case():
    assert stray_hosts(page("https://MC.YANDEX.RU/metrika/tag.js")) == []


# ─── What it must go on refusing ─────────────────────────────────────────────


def test_another_outside_host_is_still_caught():
    """The exception is for one host, and the rule it stands in survives it."""
    stray = stray_hosts(page("https://fonts.googleapis.com/css?family=Inter"))
    assert stray == ["https://fonts.googleapis.com/css?family=Inter"]


def test_a_host_that_merely_begins_with_the_permitted_one_is_caught():
    """The trap a prefix comparison walks into.

    `https://mc.yandex.ru.example.com/x` begins with the permitted address and
    belongs to somebody else entirely. A rule that can be walked around by adding
    a dot is not a rule.
    """
    stray = stray_hosts(page(f"https://{COUNTER_HOST}.example.com/x"))
    assert stray == [f"https://{COUNTER_HOST}.example.com/x"]


def test_the_portal_name_inside_another_host_is_caught():
    stray = stray_hosts(page(f"https://{PORTAL_HOST}.evil.example/js"))
    assert stray == [f"https://{PORTAL_HOST}.evil.example/js"]


def test_a_stray_address_is_reported_whole():
    """A reader of the failure needs to see what the page would fetch."""
    stray = stray_hosts(page("https://cdn.example.com/a.js", "https://cdn.example.com/b.js"))
    assert stray == ["https://cdn.example.com/a.js", "https://cdn.example.com/b.js"]


# ─── The list itself ─────────────────────────────────────────────────────────


def test_the_permitted_set_holds_the_portal_and_the_counter_and_nothing_else():
    """The exception is enumerated, so widening it is a deliberate act.

    Without this the list could grow a host at a time and no test would notice
    that the portal had become dependent on another platform.
    """
    assert set(ALLOWED_HOSTS) == {PORTAL_HOST, COUNTER_HOST}
