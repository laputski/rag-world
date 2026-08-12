"""Сборщик каталога Papers with Code.

Каталог опасен ровно тем, чем полезен: он отвечает кодом 200 почти на всё.
Часть параметров он молча игнорирует и возвращает ленту свежайших работ всей
области, а такой ответ неотличим от осмысленного. Сборщик, доверившийся ему,
приписывал бы записям чужие свидетельства и делал бы это тихо.

Проверки строятся на записанных ответах: две настоящие карточки (работа с
площадкой публикации и препринт без неё) и настоящая недельная лента.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.collectors import paperswithcode as pwc  # noqa: E402
from tests.support import FakeTransport, SourceBehaviour, load_fixture  # noqa: E402

TODAY = date(2026, 8, 12)


def fixture(name: str) -> bytes:
    return load_fixture(name)


def routes(**overrides: SourceBehaviour) -> FakeTransport:
    base = {"paperswithcode.co": SourceBehaviour(fixture("pwc_paper_preprint.json"))}
    base.update(overrides)
    return FakeTransport(base)


# ─── Ответ обязан отвечать на заданный вопрос ────────────────────────────────


def test_paper_with_another_identifier_is_refused():
    """Каталог отвечает лентой свежайших работ на игнорируемый параметр.

    Ответ выглядит осмысленным: код 200, знакомая структура, настоящая работа.
    Не совпадает только то, ради чего обращались.
    """
    http = routes(**{"paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))})
    paper, error = pwc.fetch_paper("2405.14831", http=http)

    assert paper is None
    assert error and "не о том, о чём спрошено" in error


def test_paper_with_the_requested_identifier_is_accepted():
    paper, error = pwc.fetch_paper("2405.14831", http=routes())
    assert error is None
    assert paper is not None
    assert paper.arxiv_id == "2405.14831"
    assert "HippoRAG" in paper.title


def test_absent_paper_is_not_an_error():
    """Работы в каталоге нет — это ответ, а не сбой прохода."""
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=404)})
    paper, error = pwc.fetch_paper("9999.99999", http=http)
    assert paper is None
    assert error is None


def test_broken_answer_does_not_raise():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour("{не json".encode())})
    paper, error = pwc.fetch_paper("2405.14831", http=http)
    assert paper is None
    assert error and "некорректный ответ" in error


def test_refusal_is_reported_not_swallowed():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    paper, error = pwc.fetch_paper("2405.14831", http=http)
    assert paper is None
    assert error and "503" in error


# ─── Свидетельство о площадке ────────────────────────────────────────────────


def test_venue_becomes_evidence():
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))
    })
    result = pwc.collect_venue("rag_original", "2005.11401", http=http, today=TODAY)

    assert result.errors == []
    assert len(result.evidence) == 1
    item = result.evidence[0]
    assert item.type == "publication"
    assert "venue=NeurIPS" in item.value
    assert "peer_reviewed=true" in item.value
    assert item.source.startswith("https://paperswithcode.co/api/v1/papers/")
    assert item.fetched_at == TODAY


def test_preprint_without_a_venue_yields_no_evidence():
    """Отсутствие сведения о площадке не то же самое, что сведение о её отсутствии.

    Свидетельство типа «публикация» без площадки утверждало бы ровно то, что
    уже утверждает препринт, и второй раз засчитывалось бы в уверенность.
    """
    result = pwc.collect_venue("hipporag", "2405.14831", http=routes(), today=TODAY)
    assert result.errors == []
    assert result.evidence == []


def test_citation_counter_is_named_in_the_value():
    """Каталог считает цитирования иначе, чем открытый индекс.

    У HippoRAG здесь почти триста, а в открытом индексе шестьдесят шесть: это
    разные счётчики одной работы. Не назвать счётчик значило бы показать
    читателю два числа под одним именем.
    """
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_paper_with_venue.json"))
    })
    value = pwc.collect_venue("x", "2005.11401", http=http, today=TODAY).evidence[0].value
    assert "citations_semantic_scholar=" in value
    assert "cited_by=" not in value, (
        "имя поля открытого индекса означало бы, что счётчик тот же самый"
    )


def test_citation_count_does_not_enter_the_metric_series():
    """Внимание считается по одному счётчику, иначе величины несравнимы.

    Правило берёт наибольшее значение по источникам; два счётчика одной работы
    под этим правилом систематически завышали бы внимание.
    """
    source = (ROOT / "services" / "collectors" / "paperswithcode.py").read_text(
        encoding="utf-8"
    )
    assert "MetricPoint" not in source
    assert "citation_velocity" not in source


# ─── Лента обнаружения ───────────────────────────────────────────────────────


def test_discovery_returns_the_week_of_papers():
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_discovery.json"))
    })
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))

    assert problems == []
    assert found, "лента за неделю пуста, хотя в записанном ответе работы есть"
    assert all(p.published >= date(2026, 8, 1) for p in found)
    assert all(p.arxiv_id for p in found)


def test_discovery_refuses_papers_older_than_asked():
    """Параметр даты каталог может не применить, и лента станет чужой."""
    payload = json.loads(fixture("pwc_discovery.json"))
    payload["results"][0]["published"] = "2024-01-01T00:00:00Z"
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(json.dumps(payload).encode())
    })

    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))

    assert any("параметр даты не применён" in p for p in problems)
    assert all(p.published >= date(2026, 8, 1) for p in found)


def test_discovery_survives_a_missing_list():
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b'{"count": 3}')})
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))
    assert found == []
    assert problems and "без перечня работ" in problems[0]


def test_empty_week_is_not_a_problem():
    """Неделя без новых работ обычное дело, и жалобы она не заслуживает."""
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(b'{"count": 0, "results": []}')
    })
    found, problems = pwc.discover(http=http, published_after=date(2026, 8, 1))
    assert found == []
    assert problems == []


def test_discovery_asks_the_catalogue_by_method_and_date():
    """Запрос идёт по метке метода: полнотекстовый поиск даёт вдесятеро больше шума."""
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(fixture("pwc_discovery.json"))
    })
    pwc.discover(http=http, published_after=date(2026, 8, 1))

    asked = http.calls_matching("paperswithcode.co")
    assert len(asked) == 1
    assert "method=rag" in asked[0]
    assert "published_after=2026-08-01" in asked[0]


# ─── Домен под правилом сбора ────────────────────────────────────────────────


def test_catalogue_host_is_allowed():
    from services.collectors.base import is_allowed_host

    assert is_allowed_host(pwc.PWC_API)


def test_foreign_host_is_refused(monkeypatch):
    monkeypatch.setattr(pwc, "PWC_API", "https://example.org/api/v1")
    paper, error = pwc.fetch_paper("2405.14831", http=routes())
    assert paper is None
    assert error and "allowlist" in error


@pytest.mark.parametrize("venue,expected", [
    ("NeurIPS 2020 12", True),
    ("ICLR 2024", True),
    ("", False),
])
def test_venue_year_marks_peer_review(venue, expected):
    """Год в названии сборника отличает состоявшуюся публикацию от заготовки."""
    payload = json.loads(fixture("pwc_paper_with_venue.json"))
    payload["proceeding"] = venue
    parsed = pwc.parse_paper(payload)
    assert (parsed.venue is not None) == bool(venue)
    if venue:
        assert bool(pwc._VENUE_YEAR.search(parsed.venue)) is expected
