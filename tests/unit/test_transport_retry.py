"""Поведение транспорта при отказах и ограничении частоты.

Вежливость к источникам — не украшение: архив препринтов отвечает отказом при
слишком частых обращениях, и автономный прогон, не умеющий ждать и повторять,
тихо теряет данные каждую неделю. Отказ по частоте отличается от прочих тем, что
он временный, поэтому обрабатывается иначе — повтором с растущей паузой.

Сон и сама сеть подменяются: тест не должен ни ждать, ни ходить наружу.
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
    """Паузы записываются, но не выдерживаются."""
    slept: list[float] = []
    monkeypatch.setattr(tr.time, "sleep", slept.append)
    return slept


@pytest.fixture
def responses(monkeypatch):
    """Очередь ответов сети; фактические обращения записываются."""
    queue: list[FakeResponse] = []
    calls: list[str] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return queue.pop(0) if queue else FakeResponse(200)

    monkeypatch.setattr(tr.requests, "get", fake_get)
    return queue, calls


URL = "https://api.openalex.org/works/W1"


def test_rate_limit_is_retried_until_success(no_sleep, responses):
    """Отказ по частоте — временный, поэтому обращение повторяется."""
    queue, calls = responses
    queue.extend([
        FakeResponse(429), FakeResponse(429), FakeResponse(200, b'{"ok": true}')
    ])

    status, body = tr.RequestsTransport().get(URL)

    assert status == 200
    assert body == b'{"ok": true}'
    assert len(calls) == 3, "два отказа — два повтора"


def test_pause_grows_between_retries(no_sleep, responses, monkeypatch):
    """Пауза растёт: повтор с той же частотой снова упрётся в тот же запрет.

    Пауза вежливости здесь отключена, иначе она перемешивается с паузой отката
    и запись становится нечитаемой.
    """
    monkeypatch.setattr(tr.RequestsTransport, "_wait", lambda self, host: None)
    queue, _ = responses
    queue.extend([FakeResponse(429), FakeResponse(429), FakeResponse(200)])

    tr.RequestsTransport().get(URL)

    assert len(no_sleep) == 2, f"ожидались две паузы отката: {no_sleep}"
    assert no_sleep[1] > no_sleep[0], f"паузы не растут: {no_sleep}"


def test_retries_are_bounded(no_sleep, responses):
    """Источник, отвечающий отказом всегда, не должен держать прогон вечно."""
    queue, calls = responses
    queue.extend([FakeResponse(429)] * 50)

    status, _ = tr.RequestsTransport().get(URL)

    assert status == 429, "исчерпав повторы, транспорт отдаёт отказ, а не молчит"
    assert len(calls) == tr.RETRIES_ON_RATE_LIMIT + 1


def test_other_failures_are_not_retried(no_sleep, responses):
    """Отсутствующая страница повтором не появится: повтор здесь — трата."""
    queue, calls = responses
    queue.extend([FakeResponse(404), FakeResponse(200)])

    status, _ = tr.RequestsTransport().get(URL)

    assert status == 404
    assert len(calls) == 1


def test_network_error_is_reported_not_raised(no_sleep, monkeypatch):
    """Обрыв сети — отказ одного источника, а не падение всего прогона."""
    def boom(url, headers=None, timeout=None):
        raise tr.requests.RequestException("сеть недоступна")

    monkeypatch.setattr(tr.requests, "get", boom)
    status, body = tr.RequestsTransport().get(URL)

    assert status == 0
    assert b"\xd1\x81\xd0\xb5\xd1\x82\xd1\x8c" in body or body


def test_foreign_host_is_never_contacted(no_sleep, responses):
    """Перечень доменов проверяется до обращения, а не после."""
    _, calls = responses

    status, _ = tr.RequestsTransport().get("https://example.invalid/steal")

    assert status == 403
    assert calls == [], "к постороннему адресу обращения не было"


def test_polite_delay_is_kept_between_calls(no_sleep, responses):
    """Между обращениями к одному хосту выдерживается пауза."""
    http = tr.RequestsTransport()
    http.get("https://export.arxiv.org/api/query?id_list=1")
    http.get("https://export.arxiv.org/api/query?id_list=2")

    assert any(w > 0 for w in no_sleep), "второе обращение пошло без паузы"
