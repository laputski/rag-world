"""Тесты определения площадки публикации и отбора совпадений.

Здесь закрепляются два свойства, без которых реестру нельзя доверять.

Первое: рецензирование распознаётся даже тогда, когда индекс не заполнил
название площадки. Иначе конференционные публикации навсегда остались бы
препринтами и не достигали бы подтверждённого уровня.

Второе: ненадёжное совпадение по названию не порождает свидетельства. При
разработке сборщик успел подобрать к Self-RAG постороннюю работу; молчаливая
подстановка чужих сведений опаснее отсутствия данных.
"""

from __future__ import annotations

import json
from datetime import date

from services.collectors.openalex import _venue_of, collect_openalex


class FakeHttp:
    """Заглушка транспорта: отдаёт заранее заданные ответы по подстроке адреса."""

    def __init__(self, routes: dict[str, dict], status: int = 200):
        self.routes = routes
        self.status = status
        self.calls: list[str] = []

    def get(self, url: str, headers=None, timeout: int = 20) -> tuple[int, bytes]:
        self.calls.append(url)
        for marker, payload in self.routes.items():
            if marker in url:
                return (self.status, json.dumps(payload).encode())
        return (404, b"{}")


TODAY = date(2026, 8, 8)


def _work(**kwargs) -> dict:
    base = {
        "id": "https://openalex.org/W1",
        "title": "Adaptive-RAG: Learning to Adapt Retrieval",
        "type": "preprint",
        "doi": "https://doi.org/10.48550/arxiv.2403.14403",
        "cited_by_count": 10,
        "publication_year": 2024,
        "publication_date": "2024-03-21",
        "primary_location": {"source": {"display_name": "arXiv (Cornell University)",
                                        "type": "repository"}},
        "locations": [],
    }
    base.update(kwargs)
    return base


# ─── Распознавание площадки ──────────────────────────────────────────────────


def test_repository_source_is_not_peer_reviewed():
    venue, reviewed = _venue_of(_work())
    assert reviewed is False
    assert "arXiv" in venue


def test_conference_source_is_peer_reviewed():
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        primary_location={"source": {"display_name": "NAACL", "type": "conference"}},
    )
    assert _venue_of(work) == ("NAACL", True)


def test_peer_review_detected_when_venue_name_is_missing():
    """Главный случай: тип работы и издательский префикс есть, названия нет."""
    work = _work(
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        primary_location={"source": None},
        locations=[{"source": None}],
    )
    venue, reviewed = _venue_of(work)
    assert reviewed is True
    assert venue == "ACL Anthology"


def test_unknown_publisher_prefix_is_reported_as_is():
    work = _work(type="article", doi="https://doi.org/10.52202/something",
                 primary_location={"source": None}, locations=[])
    venue, reviewed = _venue_of(work)
    assert reviewed is True
    assert "10.52202" in venue, "издатель неизвестен — показываем префикс, а не выдумку"


def test_preprint_doi_never_counts_as_peer_reviewed():
    work = _work(type="article", doi="https://doi.org/10.48550/arxiv.2403.14403",
                 primary_location={"source": None}, locations=[])
    assert _venue_of(work)[1] is False


# ─── Отбор совпадений ────────────────────────────────────────────────────────


def test_resolved_by_identifier_and_enriched_with_reviewed_version():
    preprint = _work()
    published = _work(
        id="https://openalex.org/W2",
        type="conference-paper",
        doi="https://doi.org/10.18653/v1/2024.naacl-long.389",
        cited_by_count=183,
        primary_location={"source": None},
    )
    http = FakeHttp({
        "works/doi:10.48550": preprint,
        "title.search": {"results": [published, preprint]},
    })
    result = collect_openalex(
        "adaptive_rag", "https://arxiv.org/abs/2403.14403",
        http=http, expected_title="Adaptive RAG", today=TODAY,
    )
    assert result.errors == []
    assert len(result.evidence) == 1
    value = result.evidence[0].value
    assert "peer_reviewed=true" in value
    assert "venue=ACL Anthology" in value
    assert "cited_by=183" in value, "берётся наиболее цитируемая версия работы"


def test_foreign_work_is_rejected_instead_of_recorded():
    """Название не совпало — свидетельство не создаётся."""
    foreign = _work(id="https://openalex.org/W9", title="CareerX: A Framework",
                    cited_by_count=500)
    http = FakeHttp({"title.search": {"results": [foreign]}})
    result = collect_openalex(
        "self_rag", "https://example.org/no-identifier",
        http=http, expected_title="Self-RAG", today=TODAY,
    )
    assert result.evidence == []
    assert any("no reliable match by title" in e for e in result.errors)


def test_prefix_match_accepts_full_paper_title():
    """Имя технологии — начало заголовка работы; это допустимое совпадение."""
    work = _work(id="https://openalex.org/W3",
                 title="Self-RAG: Learning to Retrieve, Generate, and Critique")
    http = FakeHttp({"title.search": {"results": [work]}})
    result = collect_openalex(
        "self_rag", "https://example.org/no-identifier",
        http=http, expected_title="Self-RAG", today=TODAY,
    )
    assert len(result.evidence) == 1
    assert result.errors == []


def test_title_separators_do_not_break_the_query():
    """Запятая и двоеточие в названии разделяют условия фильтра индекса."""
    work = _work(title="Self-RAG: Learning to Retrieve, Generate, and Critique")
    http = FakeHttp({"works/doi:10.48550": work, "title.search": {"results": [work]}})
    collect_openalex(
        "self_rag", "https://arxiv.org/abs/2310.11511", http=http, today=TODAY,
    )
    search_calls = [c for c in http.calls if "title.search" in c]
    assert search_calls, "поиск по названию должен выполняться"
    assert "%2C" not in search_calls[0] and "%3A" not in search_calls[0]


def test_citation_velocity_is_reported_not_raw_count_only():
    work = _work(cited_by_count=60, publication_date="2026-02-08")
    http = FakeHttp({"works/doi:10.48550": work, "title.search": {"results": [work]}})
    result = collect_openalex(
        "demo", "https://arxiv.org/abs/2602.00001", http=http, today=TODAY,
    )
    # Шесть месяцев, шестьдесят цитирований — десять в месяц.
    assert "citation_velocity=10.0" in result.evidence[0].value


def test_missing_work_reports_error_without_evidence():
    http = FakeHttp({}, status=404)
    result = collect_openalex("demo", "https://arxiv.org/abs/2602.00001",
                              http=http, today=TODAY)
    assert result.evidence == []
    assert result.errors


def test_title_with_a_question_mark_does_not_break_the_query():
    """Знаки подстановки в названии работы делают запрос недопустимым.

    Индекс считает `?` и `*` подстановкой и отвечает кодом 400, а работа молча
    остаётся без сведений о площадке — то есть навсегда препринтом. Названий с
    вопросительным знаком в области полно: «What Retrieval Granularity Should
    We Use?» — одно из них.
    """
    import re

    for title, expected in [
        ("Dense X Retrieval: What Granularity Should We Use?",
         "Dense X Retrieval  What Granularity Should We Use"),
        ("RAG or Long Context? A Comparison", "RAG or Long Context  A Comparison"),
        ("Foo * Bar", "Foo   Bar"),
    ]:
        cleaned = re.sub(r"[,|:?*]+", " ", title).strip()
        assert cleaned == expected, cleaned
        assert not set("?*:,|") & set(cleaned), f"остались разделители: {cleaned!r}"
