"""Очередь кандидатов: обнаружение не заводит записей.

Найденная работа — предположение, а не технология. Правило, решающее «это новая
архитектура, а не приложение существующей», ошибается, и цена ошибки — запись
реестра о том, чего нет. Поэтому обнаружение только дописывает очередь, а
решение остаётся за человеком.

Отсев проверяется отдельно: кандидат, уже описанный реестром либо однажды
отклонённый, не должен всплывать снова ни при каком числе прогонов.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import discover  # noqa: E402

from services.registry import store  # noqa: E402
from tests.support import FakeTransport, SourceBehaviour, load_fixture  # noqa: E402

TODAY = date(2026, 8, 12)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for name, path in (
        ("DATA_DIR", tmp_path),
        ("TECHNOLOGIES_DIR", tmp_path / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "evidence"),
        ("METRICS_DIR", tmp_path / "metrics"),
        ("LEVELS_FILE", tmp_path / "levels" / "history.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    (tmp_path / "technologies").mkdir(parents=True)
    monkeypatch.setattr(discover, "CANDIDATES", tmp_path / "candidates.jsonl")
    monkeypatch.setattr(discover, "REJECTED", tmp_path / "rejected.jsonl")
    return tmp_path


def feed() -> FakeTransport:
    return FakeTransport({
        "paperswithcode.co": SourceBehaviour(load_fixture("pwc_discovery.json"))
    })


def first_paper() -> dict:
    return json.loads(load_fixture("pwc_discovery.json"))["results"][0]


# ─── Обнаружение не трогает реестр ───────────────────────────────────────────


def test_discovery_creates_no_registry_records(workspace):
    """Главное свойство ступени: она предлагает, а не решает."""
    before = len(store.load_technologies())
    discover.run(http=feed(), today=TODAY, since_days=30)
    assert len(store.load_technologies()) == before == 0


def test_found_papers_land_in_the_queue(workspace):
    summary = discover.run(http=feed(), today=TODAY, since_days=30)

    assert summary.found > 0
    assert summary.added == summary.found
    rows = discover.load_candidates()
    assert len(rows) == summary.added
    assert all(row["verdict"] is None for row in rows), (
        "вердикт проставляет человек, а не обнаружение"
    )
    assert all(row["found_at"] == TODAY.isoformat() for row in rows)
    assert all(row["source"].startswith("https://paperswithcode.co/") for row in rows)


def test_dry_run_writes_nothing(workspace):
    discover.run(http=feed(), today=TODAY, since_days=30, dry_run=True)
    assert discover.load_candidates() == []


# ─── Отсев ───────────────────────────────────────────────────────────────────


def test_paper_already_in_the_registry_is_skipped(workspace):
    """Реестр узнаётся по номеру препринта в ссылке."""
    paper = first_paper()
    store.save_technology(store.Technology(
        id="known", name="Known", kind="architecture", groups=["A"],
        links=[store.Link(url=f"https://arxiv.org/abs/{paper['arxiv_id']}",
                          kind="preprint")],
    ))
    summary = discover.run(http=feed(), today=TODAY, since_days=30)

    assert summary.known >= 1
    assert paper["arxiv_id"] not in {r["arxiv_id"] for r in discover.load_candidates()}


def test_paper_matching_a_registry_name_is_skipped(workspace):
    """Имя работы обычно длиннее имени технологии и стоит до двоеточия."""
    paper = first_paper()
    head = paper["title"].split(":", 1)[0].strip()
    store.save_technology(store.Technology(
        id="known", name=head, kind="architecture", groups=["A"],
    ))
    summary = discover.run(http=feed(), today=TODAY, since_days=30)
    assert summary.known >= 1


def test_once_rejected_name_does_not_return(workspace):
    """Отклонённое имя всплывало бы каждую неделю, и работа повторялась бы."""
    paper = first_paper()
    head = paper["title"].split(":", 1)[0].strip()
    discover.REJECTED.write_text(
        json.dumps({"name": head, "reason": "приложение, а не архитектура"},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = discover.run(http=feed(), today=TODAY, since_days=30)
    assert summary.known >= 1


def test_candidate_with_a_verdict_does_not_return(workspace):
    paper = first_paper()
    discover.CANDIDATES.write_text(
        json.dumps({"arxiv_id": paper["arxiv_id"], "title": paper["title"],
                    "verdict": "rejected"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = discover.run(http=feed(), today=TODAY, since_days=30)
    assert summary.decided >= 1
    assert sum(1 for r in discover.load_candidates()
               if r["arxiv_id"] == paper["arxiv_id"]) == 1


def test_second_run_does_not_duplicate_the_queue(workspace):
    discover.run(http=feed(), today=TODAY, since_days=30)
    first = len(discover.load_candidates())
    discover.run(http=feed(), today=TODAY, since_days=30)
    assert len(discover.load_candidates()) == first


# ─── Отказ источника ─────────────────────────────────────────────────────────


def test_catalogue_refusal_does_not_break_the_pass(workspace):
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    summary = discover.run(http=http, today=TODAY, since_days=30)

    assert summary.added == 0
    assert summary.problems, "отказ каталога обязан попасть в отчёт"
    assert discover.load_candidates() == []


def test_rescoring_keeps_the_curated_signal(tmp_path, monkeypatch):
    """Пересчёт не должен терять признак, выведенный при находке.

    Оценка пересчитывается по строке очереди, а не по источнику, поэтому всё,
    что влияет на неё, обязано лежать в самой строке и передаваться обратно.
    Один раз так и вышло: работы, найденные по курируемым спискам, теряли
    признак включения в список при первом же пересчёте, и оценка падала на два
    очка без всякого события. Отказ тихий вдвойне — очередь остаётся на месте,
    меняется только порядок просмотра.
    """
    import json as _json

    queue = tmp_path / "candidates.jsonl"
    row = {
        "arxiv_id": "2510.10114",
        "title": "LinearRAG: Linear Graph Retrieval Augmented Generation",
        "abstract": "A linear index over entities with graph traversal, reranking and embeddings.",
        "tasks": [],
        "curated_by": ["Awesome-GraphRAG"],
        "fit": {"score": 0, "signals": []},
        "verdict": None,
    }
    queue.write_text(_json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(discover, "CANDIDATES", queue)

    discover.rescore()

    after = _json.loads(queue.read_text(encoding="utf-8").strip())
    codes = [signal["code"] for signal in after["fit"]["signals"]]
    assert "curatedList" in codes, (
        "признак включения в курируемый список потерян при пересчёте"
    )
    assert after["fit"]["score"] >= 4
