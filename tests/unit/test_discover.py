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


def test_a_discarded_work_is_not_counted_as_a_refusal(workspace):
    """The catalogue answers and the window check drops what it returned.

    Counted as refusals, those drops made a run log say that the source had
    yielded nothing several dozen times a week, when it had answered every time.
    The pass now reports them apart, and the run log keeps only refusals.
    """
    import json as _json
    payload = _json.loads(load_fixture("pwc_discovery.json"))
    for row in payload["results"]:
        row["published"] = "2020-01-01T00:00:00Z"
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(_json.dumps(payload).encode())
    })
    summary = discover.run(http=http, today=TODAY, since_days=30)

    assert summary.discarded, "the dropped works have to be reported somewhere"
    assert "paperswithcode" not in summary.failures, (
        f"a work the check dropped is counted as a refusal: {dict(summary.failures)}"
    )
    assert not any("the date parameter was not applied" in p for p in summary.problems), (
        "a discarded work must not appear among the refusals"
    )


def test_a_refusal_is_counted_against_the_source_that_made_it(workspace):
    """Discovery asks two sources, and a step is not a source.

    The run log records which source yielded nothing. While both routes were
    counted under one name, a pass reporting forty-seven refusals said that
    «discovery» had refused, when what had happened was that one catalogue
    ignored the date it was asked for.
    """
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    summary = discover.run(http=http, today=TODAY, since_days=30)

    assert "paperswithcode" in summary.failures, (
        f"the refusing source is not named: {dict(summary.failures)}"
    )
    assert "discovery" not in summary.failures, (
        "the name of the step must not stand in for the name of a source"
    )


def test_the_counts_of_refusals_add_up_to_their_messages(workspace):
    """Two numbers about the same events must not disagree.

    The messages go to a person reading the pass, the counts go to the run log,
    and if they can diverge a reader has to guess which of the two to believe.
    """
    http = FakeTransport({"paperswithcode.co": SourceBehaviour(b"", status=503)})
    summary = discover.run(http=http, today=TODAY, since_days=30)

    assert sum(summary.failures.values()) == len(summary.problems)


def test_a_source_that_answered_is_not_named_among_the_refusals(workspace):
    """The other side: a breakdown that accuses everyone accuses no one.

    Under the standard answers the catalogue replies and only the markup of the
    curated list is missing, so exactly one of the two may be named. A key
    standing at zero would be the same fault in another form: it asserts that a
    source refused nothing, where nothing is what should be said.
    """
    summary = discover.run(http=feed(), today=TODAY, since_days=30)

    assert sum(summary.failures.values()) == len(summary.problems)
    assert "paperswithcode" not in summary.failures, (
        f"the catalogue answered and must not be listed: {dict(summary.failures)}"
    )
    assert all(count > 0 for count in summary.failures.values()), (
        f"a refusal count standing at zero: {dict(summary.failures)}"
    )


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


# ─── Several routes and several lists in one pass ────────────────────────────
#
# Found on 2026-09-22 and reproduced before being fixed: every find from a list
# was credited to every list, a work held by two lists or found by two routes
# entered the queue two or three times, a refused batch counted as one refusal
# per work in it, and an archive answering with something that is not a feed
# looked like a quiet week.

AWESOME = "raw.githubusercontent.com/DEEP-PolyU"
SURVEY = "raw.githubusercontent.com/Graph-RAG"


def _markup(*ids: str) -> bytes:
    return "".join(
        f"- (arXiv 2026) **Work {n}** [[Paper]](https://arxiv.org/abs/{arxiv_id})\n"
        for n, arxiv_id in enumerate(ids)
    ).encode()


def _atom(*works: tuple[str, str, str]) -> bytes:
    """Entries of the archive: (identifier, date of submission, title)."""
    entries = "".join(
        f"<entry><id>http://arxiv.org/abs/{arxiv_id}v1</id>"
        f"<published>{published}T12:00:00Z</published>"
        f"<title>{title}</title><summary>Retrieval-augmented generation.</summary></entry>"
        for arxiv_id, published, title in works
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>'
    ).encode()


def _quiet_catalogue() -> SourceBehaviour:
    return SourceBehaviour(json.dumps({"results": []}).encode())


def test_a_find_is_credited_only_to_the_lists_that_hold_it(workspace):
    http = FakeTransport({
        "paperswithcode.co": _quiet_catalogue(),
        AWESOME: SourceBehaviour(_markup("2601.00001", "2601.00003")),
        SURVEY: SourceBehaviour(_markup("2601.00002", "2601.00003")),
        "search_query": SourceBehaviour(_atom()),
        "id_list": SourceBehaviour(_atom(
            ("2601.00001", "2026-01-05", "Alpha: one"),
            ("2601.00002", "2026-01-05", "Beta: two"),
            ("2601.00003", "2026-01-05", "Gamma: three"),
        )),
    })
    discover.run(http=http, today=TODAY)

    rows = {row["arxiv_id"]: row for row in discover.load_candidates()}
    assert len(discover.load_candidates()) == 3, "a work entered the queue twice"
    assert rows["2601.00001"]["curated_by"] == ["Awesome-GraphRAG"]
    assert rows["2601.00002"]["curated_by"] == ["Graph-RAG survey list"]
    assert rows["2601.00003"]["curated_by"] == [
        "Awesome-GraphRAG", "Graph-RAG survey list",
    ]
    asked_for_gamma = [c for c in http.calls_matching("id_list") if "2601.00003" in c]
    assert len(asked_for_gamma) == 1, "a work held by two lists was fetched twice"


def test_a_work_found_by_two_routes_is_queued_once(workspace):
    paper = first_paper()
    http = FakeTransport({
        "paperswithcode.co": SourceBehaviour(load_fixture("pwc_discovery.json")),
        AWESOME: SourceBehaviour(b""),
        SURVEY: SourceBehaviour(b""),
        "search_query": SourceBehaviour(_atom(
            (paper["arxiv_id"], TODAY.isoformat(), "Named: the same work"),
        )),
    })
    discover.run(http=http, today=TODAY, since_days=30)

    same = [r for r in discover.load_candidates() if r["arxiv_id"] == paper["arxiv_id"]]
    assert len(same) == 1
    assert same[0]["found_by"] == "catalogue", (
        "the copy kept is the catalogue's, and its task tags are what it was scored by"
    )


def test_the_archive_reaches_back_past_the_announcement_lag(workspace):
    """A Friday-evening submission is announced after the Monday pass.

    By the next Monday its date lies ten days back, outside an eight-day
    window, and until 2026-09-22 no pass ever saw it.
    """
    monday = date(2026, 9, 21)
    friday_before_last = date(2026, 9, 11)
    http = FakeTransport({
        "paperswithcode.co": _quiet_catalogue(),
        AWESOME: SourceBehaviour(b""),
        SURVEY: SourceBehaviour(b""),
        "search_query": SourceBehaviour(_atom(
            ("2609.11111", friday_before_last.isoformat(), "FriRAG: announced on Monday"),
        )),
    })
    discover.run(http=http, today=monday)

    assert [r["arxiv_id"] for r in discover.load_candidates()] == ["2609.11111"]


def test_a_refused_batch_is_one_refusal(workspace):
    # The second list holds only a work already in the queue, so it asks the
    # archive nothing and cannot add a refusal of its own.
    discover.CANDIDATES.write_text(
        json.dumps({"arxiv_id": "2601.00009", "title": "Queued: already",
                    "verdict": None}) + "\n",
        encoding="utf-8",
    )
    http = FakeTransport({
        "paperswithcode.co": _quiet_catalogue(),
        AWESOME: SourceBehaviour(_markup("2601.00001", "2601.00002", "2601.00003")),
        SURVEY: SourceBehaviour(_markup("2601.00009")),
        "search_query": SourceBehaviour(_atom()),
        "id_list": SourceBehaviour(b"", status=503),
    })
    summary = discover.run(http=http, today=TODAY)

    assert summary.failures["curated_lists"] == 1, summary.problems


def test_an_archive_answer_that_is_not_a_feed_is_a_refusal(workspace):
    http = FakeTransport({
        "paperswithcode.co": _quiet_catalogue(),
        AWESOME: SourceBehaviour(b""),
        SURVEY: SourceBehaviour(b""),
        "search_query": SourceBehaviour(b"<html><body>Service unavailable</body>"),
    })
    summary = discover.run(http=http, today=TODAY)

    assert summary.failures["arxiv"] == 1, summary.failures
