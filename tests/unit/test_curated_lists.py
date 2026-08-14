"""Обнаружение по курируемым спискам: разбор разметки и поведение при отказах.

Источник здесь не служба с договором, а файл, который человек правит руками.
Отсюда два рода отказа, которых у прочих сборщиков нет. Список может сменить
форму записи, и разбор молча вернёт пустоту, выглядя при этом работающим. И
список может содержать сотню работ, из которых новых единицы, поэтому отсев
обязан идти **до** обращения к arXiv, иначе каждый прогон бьёт по чужой службе
впустую.

Проверяется всё на записанной разметке. Ставить проверку в зависимость от того,
что сегодня лежит в чужом репозитории, значит завести тест, падающий от чужой
правки.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services.collectors.curated import (
    CuratedList,
    discover_from_lists,
    parse_entries,
)
from tests.support.fake_transport import FakeTransport, SourceBehaviour

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
MARKUP = (FIXTURES / "curated_awesome_graphrag.md").read_bytes()

LIST = CuratedList(
    name="Awesome-GraphRAG",
    readme="https://raw.githubusercontent.com/DEEP-PolyU/Awesome-GraphRAG/main/README.md",
    page="https://github.com/DEEP-PolyU/Awesome-GraphRAG",
)

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2510.10114v2</id>
    <title>LinearRAG: Linear Graph Retrieval Augmented Generation on Large-scale Corpora</title>
    <published>2025-10-11T00:00:00Z</published>
    <summary>Graph retrieval over a large corpus is expensive. We build a linear
    index over entities and traverse it without quadratic cost, improving
    reranking and recall on multi-hop benchmarks.</summary>
  </entry>
</feed>
"""


def routes(**overrides) -> dict[str, SourceBehaviour]:
    base = {
        "raw.githubusercontent.com": SourceBehaviour(body=MARKUP),
        "export.arxiv.org": SourceBehaviour(body=ATOM),
    }
    base.update(overrides)
    return base


# ─── Разбор разметки ─────────────────────────────────────────────────────────

def test_entries_are_parsed_with_identifier_venue_and_year():
    entries = parse_entries(MARKUP.decode("utf-8"))
    assert entries, "записанная разметка обязана разбираться"
    first = entries[0]
    assert first.arxiv_id == "2510.10114"
    assert first.venue == "ICLR 2026"
    assert first.year == 2026
    assert first.title.startswith("LinearRAG")


def test_entry_without_a_preprint_is_skipped_silently():
    """У работы может не быть препринта, и это не поломка списка."""
    markup = (
        "- (ACL 2024) **Something Without A Preprint** [[Paper]](https://doi.org/10.1/x)\n"
        "- (ICLR 2026) **With One** [[Paper]](https://arxiv.org/abs/2510.10114)\n"
    )
    entries = parse_entries(markup)
    assert [e.arxiv_id for e in entries] == ["2510.10114"]


def test_repeated_identifier_is_taken_once():
    markup = (
        "- (ICLR 2026) **A** [[Paper]](https://arxiv.org/abs/2510.10114)\n"
        "- (arXiv 2025) **A again** [[Paper]](https://arxiv.org/pdf/2510.10114)\n"
    )
    assert len(parse_entries(markup)) == 1


def test_free_form_lines_are_not_invented_into_entries():
    """Разбор берёт одну объявленную форму записи и не угадывает прочие.

    Попытка понять произвольную разметку кончается выдуманными заголовками,
    а выдуманный заголовок доходит до очереди кандидатов и выглядит находкой.
    """
    markup = (
        "Some prose mentioning https://arxiv.org/abs/2510.10114 in passing.\n"
        "- a plain bullet with https://arxiv.org/abs/2412.16311\n"
        "| table | https://arxiv.org/abs/2502.06864 |\n"
    )
    assert parse_entries(markup) == []


# ─── Обращение к источникам ──────────────────────────────────────────────────

def test_known_identifiers_are_filtered_before_arxiv_is_asked():
    """Список велик, новых работ единицы: лишние запросы не делаются."""
    entries = parse_entries(MARKUP.decode("utf-8"))
    everything = {entry.arxiv_id for entry in entries}
    http = FakeTransport(routes())

    papers, problems = discover_from_lists(
        http=http, lists=(LIST,), known=everything
    )

    assert papers == []
    assert problems == []
    assert http.calls_matching("export.arxiv.org") == [], (
        "все работы известны, обращаться к arXiv не за чем"
    )


def test_facts_come_from_arxiv_not_from_the_list():
    """Список пишут руками; заголовок и аннотацию даёт arXiv."""
    known = {e.arxiv_id for e in parse_entries(MARKUP.decode("utf-8"))} - {"2510.10114"}
    papers, problems = discover_from_lists(
        http=FakeTransport(routes()), lists=(LIST,), known=known
    )

    assert problems == []
    assert len(papers) == 1
    paper = papers[0]
    assert paper.arxiv_id == "2510.10114"
    assert paper.abstract.startswith("Graph retrieval over a large corpus")
    assert paper.published == date(2025, 10, 11)
    # Площадка известна только списку, поэтому берётся у него.
    assert paper.venue == "ICLR 2026"
    assert paper.url == "https://arxiv.org/abs/2510.10114"


def test_a_list_that_changed_its_form_is_reported_not_passed_over():
    """Пустой разбор при успешном ответе — отказ, а не тишина.

    Молчание здесь худший исход: сборщик выглядит работающим, очередь
    кандидатов не пополняется, и заметить это можно только через месяцы.
    """
    papers, problems = discover_from_lists(
        http=FakeTransport(routes(**{
            "raw.githubusercontent.com": SourceBehaviour(body=b"# List\n\nnothing here\n"),
        })),
        lists=(LIST,),
    )
    assert papers == []
    assert any("the shape of the list has probably changed" in problem
               for problem in problems)


@pytest.mark.parametrize("status", [404, 500, 503])
def test_unavailable_list_is_reported_and_does_not_raise(status):
    papers, problems = discover_from_lists(
        http=FakeTransport(routes(**{
            "raw.githubusercontent.com": SourceBehaviour(status=status, body=b""),
        })),
        lists=(LIST,),
    )
    assert papers == []
    assert any(str(status) in problem for problem in problems)


def test_work_arxiv_does_not_return_is_reported_and_not_invented():
    """Без аннотации кандидата нет: оценка по заголовку — догадка."""
    known = {e.arxiv_id for e in parse_entries(MARKUP.decode("utf-8"))} - {"2412.16311"}
    papers, problems = discover_from_lists(
        http=FakeTransport(routes()), lists=(LIST,), known=known
    )
    assert papers == []
    assert any("2412.16311" in problem for problem in problems)


def test_a_host_outside_the_allowlist_is_refused():
    """Перечень разрешённых доменов действует и на этот путь тоже."""
    papers, problems = discover_from_lists(
        http=FakeTransport(routes()),
        lists=(CuratedList(name="Where", readme="https://example.org/x.md", page="x"),),
    )
    assert papers == []
    assert any("outside the allowlist" in problem for problem in problems)


def test_window_keeps_older_entries_out():
    """Окно отсекает по году площадки, если он в списке указан."""
    papers, _ = discover_from_lists(
        http=FakeTransport(routes()), lists=(LIST,),
        published_after=date(2026, 1, 1),
    )
    assert all(paper.venue and "2026" in paper.venue for paper in papers)
