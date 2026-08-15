"""The candidate queue: discovery creates no records.

A work that has been found is a supposition, not a technology. The rule deciding
"this is a new architecture rather than an application of an existing one" errs,
and the price of the error is a registry record about something that does not
exist. So discovery only appends to the queue, and the decision stays a person's.

Filtering is checked separately: a candidate already in the registry or already
refused must not surface again on any number of passes.
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


# ─── Discovery does not touch the registry ───────────────────────────────────


def test_discovery_creates_no_registry_records(workspace):
    """The main property of the stage: it proposes rather than decides."""
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
        "the verdict is entered by a person, not by discovery"
    )
    assert all(row["found_at"] == TODAY.isoformat() for row in rows)
    assert all(row["source"].startswith("https://paperswithcode.co/") for row in rows)


def test_dry_run_writes_nothing(workspace):
    discover.run(http=feed(), today=TODAY, since_days=30, dry_run=True)
    assert discover.load_candidates() == []


# ─── Filtering ───────────────────────────────────────────────────────────────


def test_paper_already_in_the_registry_is_skipped(workspace):
    """The registry is recognised by the preprint number in a link."""
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
    """A work's title is usually longer than a name and stands before the colon."""
    paper = first_paper()
    head = paper["title"].split(":", 1)[0].strip()
    store.save_technology(store.Technology(
        id="known", name=head, kind="architecture", groups=["A"],
    ))
    summary = discover.run(http=feed(), today=TODAY, since_days=30)
    assert summary.known >= 1


def test_once_rejected_name_does_not_return(workspace):
    """A refused name would surface every week and the work would repeat."""
    paper = first_paper()
    head = paper["title"].split(":", 1)[0].strip()
    discover.REJECTED.write_text(
        json.dumps({"name": head, "reason": "an application, not an architecture"},
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


# ─── A source refusing ───────────────────────────────────────────────────────


def test_catalogue_refusal_does_not_break_the_pass(workspace):
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    summary = discover.run(http=http, today=TODAY, since_days=30)

    assert summary.added == 0
    assert summary.problems, "a refusal from the catalogue has to reach the report"
    assert discover.load_candidates() == []


def test_rescoring_keeps_the_curated_signal(tmp_path, monkeypatch):
    """Recomputation must not lose a signal derived at discovery.

    The score is recomputed from the queue line rather than from the source, so
    everything affecting it has to sit in that line and be handed back explicitly.
    That went wrong once: works found through curated lists lost the
    inclusion-in-a-list signal on the first recomputation, and their scores fell by
    a point with no event behind it. The failure is doubly quiet — the queue is
    there and only the order of review changes.
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
        "the curated-list signal was lost on recomputation"
    )
    assert after["fit"]["score"] >= 4
