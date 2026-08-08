"""Тесты файлового реестра.

Проверяют поведение, на которое опираются принципы проекта: свидетельства только
добавляются и не дублируются, журнал уровней растёт только при действительном
изменении уровня, отсутствие уровня отличимо от уровня L0.

Тесты работают в отдельном каталоге и настоящий реестр не трогают.
"""

from __future__ import annotations

from datetime import date

import pytest

from services.registry import store


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Подменить каталог данных на временный."""
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


# ─── Технологии ──────────────────────────────────────────────────────────────


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
    """Повторная запись той же записи не порождает изменений в файле."""
    path = store.save_technology(_tech())
    first = path.read_text(encoding="utf-8")
    store.save_technology(_tech())
    assert path.read_text(encoding="utf-8") == first


def test_unknown_field_is_rejected(data_dir):
    with pytest.raises(Exception):
        store.Technology(id="x", name="X", kind="tool", nonsense=1)


# ─── Свидетельства ───────────────────────────────────────────────────────────


def test_evidence_is_appended_and_read_back(data_dir):
    assert store.append_evidence([_evidence()]) == 1
    items = store.load_evidence()
    assert len(items) == 1
    assert items[0].type == "publication"


def test_evidence_duplicates_are_not_stored_twice(data_dir):
    store.append_evidence([_evidence()])
    added = store.append_evidence([_evidence()])
    assert added == 0, "повторный прогон сборщиков не должен раздувать журнал"
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
    """Принцип K6: существующее свидетельство не переписывается."""
    store.append_evidence([_evidence(source="first")])
    path = store.evidence_path(date(2026, 8, 1))
    before = path.read_text(encoding="utf-8")
    store.append_evidence([_evidence(source="second")])
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before)


# ─── Уровни ──────────────────────────────────────────────────────────────────


def _level(tech_id: str, level: str) -> store.LevelEntry:
    return store.LevelEntry(
        technology_id=tech_id,
        level=level,
        confidence=0.5,
        rule_version="1.0.0",
        computed_at=date(2026, 8, 1),
    )


def test_missing_level_is_distinguishable_from_l0(data_dir):
    """Отсутствие уровня — не ноль: представления обязаны это различать."""
    assert store.latest_level("demo") is None
    store.append_level(_level("demo", "L0"))
    entry = store.latest_level("demo")
    assert entry is not None and entry.level == "L0"


def test_level_journal_grows_only_on_change(data_dir):
    assert store.append_level(_level("demo", "L1")) is True
    assert store.append_level(_level("demo", "L1")) is False, (
        "пересчёт без изменения уровня не должен попадать в журнал"
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


# ─── Показатели ──────────────────────────────────────────────────────────────


def test_metrics_are_partitioned_by_year(data_dir):
    store.append_metrics([
        store.MetricPoint(
            technology_id="demo", metric="citations", value=12.0,
            measured_at=date(2026, 3, 1), source="openalex",
        )
    ])
    assert (store.METRICS_DIR / "2026.jsonl").exists()
    assert store.load_metrics("demo")[0].value == 12.0
