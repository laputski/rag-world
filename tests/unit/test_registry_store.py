"""Tests of the file-based registry.

They check the behaviour the principles of the project rest on: evidence is
appended and not duplicated, the level journal grows only when a level changes,
and an absent level is distinguishable from the level L0.

The tests work in a directory of their own and never touch the real registry.
"""

from __future__ import annotations

from datetime import date

import pytest

from services.registry import store


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Substitute a temporary directory for the data directory."""
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "TECHNOLOGIES_DIR", tmp_path / "technologies")
    monkeypatch.setattr(store, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(store, "METRICS_DIR", tmp_path / "metrics")
    monkeypatch.setattr(store, "LEVELS_FILE", tmp_path / "levels" / "history.jsonl")
    return tmp_path


def _tech(tech_id: str = "demo") -> store.Technology:
    return store.Technology(
        id=tech_id,
        name=tech_id.upper(),
        kind="architecture",
        groups=["A", "C"],
        configuration={"A4": "graph", "C1": "graph_traversal"},
        links=[store.Link(url="https://example.org/paper", kind="preprint")],
    )


def _evidence(tech_id: str = "demo", source: str = "https://example.org/paper"):
    return store.Evidence(
        technology_id=tech_id,
        type="publication",
        value="arXiv",
        source=source,
        fetched_at=date(2026, 8, 1),
        obtained_by="auto",
        verified=True,
    )


# ─── Technologies ────────────────────────────────────────────────────────────


def test_save_and_load_roundtrip(data_dir):
    store.save_technology(_tech())
    loaded = store.load_technology("demo")
    assert loaded is not None
    assert loaded.name == "DEMO"
    assert loaded.configuration["A4"] == "graph"
    assert loaded.links[0].url == "https://example.org/paper"


def test_load_technologies_is_sorted(data_dir):
    for tech_id in ("zulu", "alpha", "mike"):
        store.save_technology(_tech(tech_id))
    assert [t.id for t in store.load_technologies()] == ["alpha", "mike", "zulu"]


def test_load_missing_technology_returns_none(data_dir):
    assert store.load_technology("nothing") is None


def test_saved_file_is_stable_between_writes(data_dir):
    """Writing the same record again produces no change in the file."""
    path = store.save_technology(_tech())
    first = path.read_text(encoding="utf-8")
    store.save_technology(_tech())
    assert path.read_text(encoding="utf-8") == first


def test_unknown_field_is_rejected(data_dir):
    with pytest.raises(Exception):
        store.Technology(id="x", name="X", kind="tool", nonsense=1)


# ─── Evidence ────────────────────────────────────────────────────────────────


def test_evidence_is_appended_and_read_back(data_dir):
    assert store.append_evidence([_evidence()]) == 1
    items = store.load_evidence()
    assert len(items) == 1
    assert items[0].type == "publication"


def test_evidence_duplicates_are_not_stored_twice(data_dir):
    store.append_evidence([_evidence()])
    added = store.append_evidence([_evidence()])
    assert added == 0, "a second run of the collectors must not inflate the journal"
    assert len(store.load_evidence()) == 1


def test_evidence_is_partitioned_by_month(data_dir):
    store.append_evidence([_evidence(source="a")])
    august = store.evidence_path(date(2026, 8, 15))
    september = store.evidence_path(date(2026, 9, 15))
    assert august.exists()
    assert not september.exists()
    assert august.name == "2026-08.jsonl"


def test_evidence_filter_by_technology(data_dir):
    store.append_evidence([_evidence("one", "a"), _evidence("two", "b")])
    assert len(store.load_evidence("one")) == 1
    assert len(store.load_evidence()) == 2


def test_appending_never_rewrites_existing_lines(data_dir):
    """Existing evidence is never rewritten."""
    store.append_evidence([_evidence(source="first")])
    path = store.evidence_path(date(2026, 8, 1))
    before = path.read_text(encoding="utf-8")
    store.append_evidence([_evidence(source="second")])
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before)


# ─── Levels ──────────────────────────────────────────────────────────────────


def _level(tech_id: str, level: str) -> store.LevelEntry:
    return store.LevelEntry(
        technology_id=tech_id,
        level=level,
        confidence=0.5,
        rule_version="1.0.0",
        computed_at=date(2026, 8, 1),
    )


def test_missing_level_is_distinguishable_from_l0(data_dir):
    """An absent level is not a zero: the views have to tell them apart."""
    assert store.latest_level("demo") is None
    store.append_level(_level("demo", "L0"))
    entry = store.latest_level("demo")
    assert entry is not None and entry.level == "L0"


def test_level_journal_grows_only_on_change(data_dir):
    assert store.append_level(_level("demo", "L1")) is True
    assert store.append_level(_level("demo", "L1")) is False, (
        "a recomputation that changed nothing must not reach the journal"
    )
    assert store.append_level(_level("demo", "L2")) is True
    assert [e.level for e in store.load_levels("demo")] == ["L1", "L2"]


def test_latest_level_returns_the_last_entry(data_dir):
    store.append_level(_level("demo", "L1"))
    store.append_level(_level("demo", "L3"))
    entry = store.latest_level("demo")
    assert entry is not None and entry.level == "L3"


def test_levels_of_different_technologies_do_not_mix(data_dir):
    store.append_level(_level("one", "L1"))
    store.append_level(_level("two", "L4"))
    assert store.latest_level("one").level == "L1"
    assert store.latest_level("two").level == "L4"


# ─── Measurements ────────────────────────────────────────────────────────────


def test_metrics_are_partitioned_by_year(data_dir):
    store.append_metrics([
        store.MetricPoint(
            technology_id="demo", metric="citations", value=12.0,
            measured_at=date(2026, 3, 1), source="openalex",
        )
    ])
    assert (store.METRICS_DIR / "2026.jsonl").exists()
    assert store.load_metrics("demo")[0].value == 12.0


# ─── Reading a configuration: the residual vocabulary and the review date ────
#
# A residual exists for the sake of counting: a mechanism met in three records is
# a candidate dimension. Free text destroys that count, because one mechanism gets
# as many names as it has authors.


def test_residual_vocabulary_is_readable_and_unique():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "residual_vocabulary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mechanisms = payload["mechanisms"]

    codes = [m["id"] for m in mechanisms]
    assert len(codes) == len(set(codes)), "repeated mechanism codes"
    for mechanism in mechanisms:
        assert mechanism["ru"].strip(), f"{mechanism['id']}: the wording is empty"
        assert mechanism["en"].strip(), f"{mechanism['id']}: no English wording"
        assert mechanism["note"].strip(), (
            f"{mechanism['id']}: it does not say why the schema fails to express it"
        )


def test_free_text_residual_is_rejected(tmp_path, monkeypatch):
    """A wording outside the vocabulary has to stop the pass."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import validate_data

    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "TECHNOLOGIES_DIR", tmp_path / "technologies")
    monkeypatch.setattr(store, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(store, "METRICS_DIR", tmp_path / "metrics")
    monkeypatch.setattr(store, "LEVELS_FILE", tmp_path / "levels" / "history.jsonl")

    store.save_technology(store.Technology(
        id="freetext", name="Free", kind="tool", groups=["A"],
        residual=["some mechanism of my own, in my own words"],
    ))
    problems = validate_data.check_registry()
    assert any("residual_vocabulary" in p for p in problems), problems


def test_reviewed_date_distinguishes_default_from_unexamined():
    """"Matches the base configuration" and "nobody looked" are different claims."""
    unexamined = store.Technology(id="a", name="A", kind="tool")
    assert unexamined.configuration_reviewed is None

    from datetime import date
    examined = store.Technology(
        id="b", name="B", kind="tool",
        configuration={"A1": "passage"},
        configuration_reviewed=date(2026, 8, 9),
    )
    assert examined.configuration_reviewed is not None


def test_variable_and_inapplicable_are_separate_statements():
    """Three different claims about a dimension, not two.

    "The value is this", "the value is chosen at run time" and "the dimension does
    not apply" are different things. The schema stores one value, so the latter
    two are marks; without them a record occupies one cell of the space while it
    occupies several or none.
    """
    tech = store.Technology(
        id="x", name="X", kind="architecture",
        configuration={"C2": "iterative_stopping"},
        configuration_variable=["C2"],
        configuration_inapplicable=["E1"],
    )
    assert "C2" in tech.configuration, "a variable dimension does carry a value"
    assert "E1" not in tech.configuration, "an inapplicable one carries none"


def test_plain_record_carries_no_marks():
    """The marks are the exception; an ordinary record stays a point of the space."""
    tech = store.Technology(id="y", name="Y", kind="architecture")
    assert tech.configuration_variable == []
    assert tech.configuration_inapplicable == []


def test_attack_is_a_kind_without_configuration():
    """An attack acts upon a RAG system rather than being one.

    It has no index, no retrieval and no synthesis, and base values would assert
    that it segments documents and searches for nearest neighbours. A rule by kind
    spares such a record an inapplicability mark on every one of twenty-six
    dimensions.
    """
    assert "attack" in store.KINDS_WITHOUT_CONFIGURATION
    tech = store.Technology(id="x", name="X", kind="attack")
    assert tech.configuration == {}


def test_system_kinds_still_occupy_the_space():
    for kind in ("paradigm", "architecture", "technique", "tool"):
        assert kind not in store.KINDS_WITHOUT_CONFIGURATION


def test_residual_vocabulary_is_bilingual():
    """The residual queue is shown to the reader, not only to the owner.

    A mechanism added without an English wording or without an explanation puts a
    Russian paragraph on an English page. On the page that is noticed by eye; at
    build time, by a check.
    """
    import json
    import re
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "residual_vocabulary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cyrillic = re.compile(r"[а-яА-ЯёЁ]{4,}")

    for mechanism in payload["mechanisms"]:
        for field in ("ru", "en", "note", "note_en"):
            assert mechanism.get(field, "").strip(), f"{mechanism['id']}: no {field} field"
        for field in ("en", "note_en"):
            assert not cyrillic.search(mechanism[field]), (
                f"{mechanism['id']}.{field}: Russian text remains in an English field"
            )
