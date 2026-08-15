"""The link check: what it changes and, more importantly, what it does not.

The main property here is restraint. A link rots in silence, so checking is
needed; but a venue also refuses a robot, a network breaks, and a server falls
over for a minute. A check that takes a temporary refusal for a disappearance
spoils the registry faster than time spoils the links.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_links  # noqa: E402

from services.registry import store  # noqa: E402
from tests.support import FakeTransport, SourceBehaviour  # noqa: E402

TODAY = date(2026, 8, 9)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    for name, path in (
        ("DATA_DIR", tmp_path),
        ("TECHNOLOGIES_DIR", tmp_path / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "evidence"),
        ("METRICS_DIR", tmp_path / "metrics"),
        ("LEVELS_FILE", tmp_path / "levels" / "history.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    return tmp_path


def make(links: list[store.Link], tech_id: str = "demo") -> None:
    store.save_technology(store.Technology(
        id=tech_id, name="Demo", kind="architecture", links=links,
    ))


def only_link(tech_id: str = "demo") -> store.Link:
    return store.load_technology(tech_id).links[0]


def run(routes: dict[str, SourceBehaviour], **kwargs):
    return check_links.run(http=FakeTransport(routes), today=TODAY, **kwargs)


# ─── Addresses that resolve ──────────────────────────────────────────────────


def test_resolvable_link_is_verified(registry):
    """A mark without a date says nothing: when was it set?"""
    make([store.Link(url="https://arxiv.org/abs/2405.14831", kind="preprint")])
    summary = run({"arxiv.org": SourceBehaviour(b"ok")})

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == TODAY
    assert summary.verified == 1


def test_redirect_counts_as_resolvable(registry):
    """A venue moving is not a source disappearing."""
    make([store.Link(url="https://example.org/moved")])
    run({"example.org": SourceBehaviour(b"", status=301)})
    assert only_link().status == "verified"


def test_host_outside_the_collector_allowlist_is_still_checked(registry):
    """The allowlist guards evidence collection, not the link check."""
    make([store.Link(url="https://qdrant.tech/documentation/")])
    summary = run({"qdrant.tech": SourceBehaviour(b"ok")})
    assert summary.verified == 1
    assert only_link().status == "verified"


# ─── Addresses that have vanished ────────────────────────────────────────────


def test_missing_page_becomes_unresolved(registry):
    make([store.Link(url="https://example.org/gone", status="verified",
                     verified_at=date(2026, 1, 1))])
    summary = run({"example.org": SourceBehaviour(b"", status=404)})

    link = only_link()
    assert link.status == "unresolved"
    assert link.verified_at is None, "the confirmation date has stopped being true"
    assert summary.gone == 1


def test_gone_link_is_reported_and_returns_failure(registry):
    make([store.Link(url="https://example.org/gone")])
    summary = run({"example.org": SourceBehaviour(b"", status=410)})
    assert any("410" in p for p in summary.problems)


# ─── Restraint: what the check does not do ───────────────────────────────────


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 503])
def test_temporary_refusal_does_not_spoil_a_verified_link(registry, status):
    """A refusal on rights or a server failure is not a vanished source.

    Publishers refuse robots constantly. A check that takes that for the death of a
    link would mark half the registry as broken in a single pass.
    """
    was = date(2026, 1, 1)
    make([store.Link(url="https://dl.acm.org/doi/10.1145/x", status="verified",
                     verified_at=was)])
    run({"dl.acm.org": SourceBehaviour(b"", status=status)})

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == was, "the date of the earlier check has to be kept"


def test_network_error_does_not_spoil_a_verified_link(registry, monkeypatch):
    was = date(2026, 1, 1)
    make([store.Link(url="https://example.org/x", status="verified", verified_at=was)])

    class Broken:
        def get(self, url, headers=None, timeout=20):
            raise OSError("the network is unreachable")

    summary = check_links.run(http=Broken(), today=TODAY)

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == was
    assert summary.problems, "a broken connection has to reach the report"


def test_unknown_outcome_does_not_promote_an_unchecked_link(registry):
    """An unclear outcome does not confirm a link that was never opened."""
    make([store.Link(url="https://example.org/x")])

    class Broken:
        def get(self, url, headers=None, timeout=20):
            raise OSError("the network is unreachable")

    check_links.run(http=Broken(), today=TODAY)
    assert only_link().status == "needs_review"


@pytest.mark.parametrize("status", [401, 402, 403, 429])
def test_refusal_gives_an_unchecked_link_a_way_out(registry, status):
    """An address closed by rights stops looking unchecked.

    A refusal on rights is deliberately not counted as the death of a link. But
    while the mark stayed unchanged too, an unchecked address stuck in "nobody
    looked" for ever: it was looked at every week, telling it from one truly never
    checked was impossible, and nobody learned of it. Three registry addresses
    lived that way for the whole of the portal's existence.

    The mark `guarded` asserts exactly what was observed: the request was made, the
    address answered, and it declined to show itself to a robot. Only a person can
    confirm it.
    """
    make([store.Link(url="https://example.org/x")])
    summary = run({"example.org": SourceBehaviour(b"", status=status)})

    link = only_link()
    assert link.status == "guarded", "the mark has to differ from 'nobody looked'"
    assert link.verified_at == TODAY, "the inspection happened and its date is known"
    assert summary.guarded == 1
    assert summary.problems, "a closed address has to reach the report of the pass"


def test_guarded_link_is_not_rechecked_while_fresh(registry):
    """A venue that refused yesterday will refuse today.

    A superfluous request for an answer already known spends somebody else's
    resources.
    """
    make([store.Link(
        url="https://example.org/x", status="guarded", verified_at=date(2026, 8, 10),
    )])
    http = FakeTransport({"example.org": SourceBehaviour(b"", status=403)})
    check_links.run(http=http, today=TODAY, stale_after=30)
    assert http.calls_matching("example.org") == []


# ─── Cost and repetition ─────────────────────────────────────────────────────


def test_same_address_is_fetched_once(registry):
    """The outcome does not depend on the record, so one request is enough."""
    url = "https://arxiv.org/abs/2405.14831"
    make([store.Link(url=url)], tech_id="one")
    make([store.Link(url=url)], tech_id="two")

    http = FakeTransport({"arxiv.org": SourceBehaviour(b"ok")})
    check_links.run(http=http, today=TODAY)
    assert len(http.calls_matching("arxiv.org")) == 1


def test_recently_verified_links_can_be_skipped(registry):
    """A weekly pass must not walk the whole registry every time."""
    make([store.Link(url="https://arxiv.org/abs/1", status="verified",
                     verified_at=TODAY - timedelta(days=3))])
    http = FakeTransport({"arxiv.org": SourceBehaviour(b"ok")})
    summary = check_links.run(http=http, today=TODAY, stale_after=30)

    assert summary.checked == 0
    assert http.calls == []


def test_stale_verification_is_rechecked(registry):
    make([store.Link(url="https://arxiv.org/abs/1", status="verified",
                     verified_at=TODAY - timedelta(days=90))])
    summary = run({"arxiv.org": SourceBehaviour(b"ok")}, stale_after=30)
    assert summary.checked == 1
    assert only_link().verified_at == TODAY


def test_dry_run_writes_nothing(registry):
    make([store.Link(url="https://example.org/gone")])
    run({"example.org": SourceBehaviour(b"", status=404)}, dry_run=True)
    assert only_link().status == "needs_review", "a dry run writes nothing"


def test_repeated_pass_changes_nothing(registry):
    make([store.Link(url="https://arxiv.org/abs/1")])
    routes = {"arxiv.org": SourceBehaviour(b"ok")}
    run(routes)
    first = store.load_technology("demo").model_dump(mode="json")
    summary = run(routes)
    assert store.load_technology("demo").model_dump(mode="json") == first
    assert summary.changed == 0, "a second pass must not touch the files"
