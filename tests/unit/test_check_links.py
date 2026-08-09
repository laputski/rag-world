"""Проверка ссылок: что она меняет и, важнее, чего не меняет.

Главное свойство здесь — сдержанность. Ссылка гниёт молча, поэтому проверять
надо; но и площадка отвечает отказом роботу, и сеть рвётся, и сервер падает на
минуту. Проверка, принимающая временный отказ за исчезновение, испортит записи
быстрее, чем время испортит ссылки.
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


# ─── Разрешимые адреса ───────────────────────────────────────────────────────


def test_resolvable_link_is_verified(registry):
    """Отметка без даты ничего не сообщает: непонятно, когда её ставили."""
    make([store.Link(url="https://arxiv.org/abs/2405.14831", kind="preprint")])
    summary = run({"arxiv.org": SourceBehaviour(b"ok")})

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == TODAY
    assert summary.verified == 1


def test_redirect_counts_as_resolvable(registry):
    """Переезд площадки — не исчезновение источника."""
    make([store.Link(url="https://example.org/moved")])
    run({"example.org": SourceBehaviour(b"", status=301)})
    assert only_link().status == "verified"


def test_host_outside_the_collector_allowlist_is_still_checked(registry):
    """Перечень доменов ограждает сбор свидетельств, а не проверку своих ссылок."""
    make([store.Link(url="https://qdrant.tech/documentation/")])
    summary = run({"qdrant.tech": SourceBehaviour(b"ok")})
    assert summary.verified == 1
    assert only_link().status == "verified"


# ─── Исчезнувшие адреса ──────────────────────────────────────────────────────


def test_missing_page_becomes_unresolved(registry):
    make([store.Link(url="https://example.org/gone", status="verified",
                     verified_at=date(2026, 1, 1))])
    summary = run({"example.org": SourceBehaviour(b"", status=404)})

    link = only_link()
    assert link.status == "unresolved"
    assert link.verified_at is None, "дата подтверждения перестала быть правдой"
    assert summary.gone == 1


def test_gone_link_is_reported_and_returns_failure(registry):
    make([store.Link(url="https://example.org/gone")])
    summary = run({"example.org": SourceBehaviour(b"", status=410)})
    assert any("410" in p for p in summary.problems)


# ─── Сдержанность: чего проверка не делает ───────────────────────────────────


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500, 503])
def test_temporary_refusal_does_not_spoil_a_verified_link(registry, status):
    """Отказ по правам или сбой сервера — не исчезновение источника.

    Издательства отвечают отказом роботам постоянно. Проверка, принимающая это
    за смерть ссылки, за один прогон пометит половину реестра испорченным.
    """
    was = date(2026, 1, 1)
    make([store.Link(url="https://dl.acm.org/doi/10.1145/x", status="verified",
                     verified_at=was)])
    run({"dl.acm.org": SourceBehaviour(b"", status=status)})

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == was, "дата прежней проверки должна сохраниться"


def test_network_error_does_not_spoil_a_verified_link(registry, monkeypatch):
    was = date(2026, 1, 1)
    make([store.Link(url="https://example.org/x", status="verified", verified_at=was)])

    class Broken:
        def get(self, url, headers=None, timeout=20):
            raise OSError("сеть недоступна")

    summary = check_links.run(http=Broken(), today=TODAY)

    link = only_link()
    assert link.status == "verified"
    assert link.verified_at == was
    assert summary.problems, "обрыв связи обязан попасть в отчёт"


def test_unknown_outcome_does_not_promote_an_unchecked_link(registry):
    """Непонятный исход не подтверждает ссылку, которую не открыли."""
    make([store.Link(url="https://example.org/x")])
    run({"example.org": SourceBehaviour(b"", status=403)})
    assert only_link().status == "needs_review"


# ─── Расход и повторы ────────────────────────────────────────────────────────


def test_same_address_is_fetched_once(registry):
    """Результат от записи не зависит, значит и обращение нужно одно."""
    url = "https://arxiv.org/abs/2405.14831"
    make([store.Link(url=url)], tech_id="one")
    make([store.Link(url=url)], tech_id="two")

    http = FakeTransport({"arxiv.org": SourceBehaviour(b"ok")})
    check_links.run(http=http, today=TODAY)
    assert len(http.calls_matching("arxiv.org")) == 1


def test_recently_verified_links_can_be_skipped(registry):
    """Еженедельный прогон не должен каждый раз обходить весь реестр."""
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
    assert only_link().status == "needs_review", "пробный проход не записывает"


def test_repeated_pass_changes_nothing(registry):
    make([store.Link(url="https://arxiv.org/abs/1")])
    routes = {"arxiv.org": SourceBehaviour(b"ok")}
    run(routes)
    first = store.load_technology("demo").model_dump(mode="json")
    summary = run(routes)
    assert store.load_technology("demo").model_dump(mode="json") == first
    assert summary.changed == 0, "второй проход не должен трогать файлы"
