"""Дайджест: пересказ вычисленного, а не рассказ о нём.

Выпуск публикуется без просмотра человеком, поэтому единственное, что его
удерживает от неправды, — отсутствие в нём выдумки. Здесь проверяется, что он
не утверждает большего, чем есть в данных, не выходит впустую и не
переписывается задним числом.

Отдельно проверяются русские числительные: «5 запись» вместо «5 записей»
подрывает доверие ко всему тексту, включая верные числа.
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

import build_digest  # noqa: E402
from services.registry import store  # noqa: E402

TODAY = date(2026, 8, 9)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    for name, path in (
        ("DATA_DIR", tmp_path),
        ("TECHNOLOGIES_DIR", tmp_path / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "evidence"),
        ("METRICS_DIR", tmp_path / "metrics"),
        ("LEVELS_FILE", tmp_path / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", tmp_path / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    return tmp_path


def add_tech(tech_id: str, name: str) -> None:
    store.save_technology(store.Technology(
        id=tech_id, name=name, kind="architecture", groups=["A"],
    ))


def add_level(tech_id: str, level: str, when: date) -> None:
    store.append_level(store.LevelEntry(
        technology_id=tech_id, level=level, confidence=0.5,
        rule_version="v1", computed_at=when,
    ))


def add_evidence(tech_id: str, kind: str, when: date, source: str) -> None:
    store.append_evidence([store.Evidence(
        technology_id=tech_id, type=kind, value=None, source=source,
        fetched_at=when, obtained_by="auto", verified=True,
    )])


# ─── Русские числительные ────────────────────────────────────────────────────


@pytest.mark.parametrize("count,expected", [
    (1, "запись"), (2, "записи"), (3, "записи"), (4, "записи"),
    (5, "записей"), (10, "записей"),
    (11, "записей"), (12, "записей"), (13, "записей"), (14, "записей"),
    (21, "запись"), (22, "записи"), (25, "записей"),
    (101, "запись"), (111, "записей"), (114, "записей"), (121, "запись"),
    (0, "записей"),
])
def test_plural_forms(count, expected):
    assert build_digest.plural(count, "запись", "записи", "записей") == expected


# ─── Что попадает в выпуск ───────────────────────────────────────────────────


def test_first_issue_covers_everything(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    add_evidence("alpha", "publication", TODAY, "https://arxiv.org/abs/1")

    issue = build_digest.build(today=TODAY)

    assert issue.since is None
    assert [i["technology_id"] for i in issue.added] == ["alpha"]
    assert issue.evidence_added == 1
    assert "Alpha" in issue.text


def test_promotion_and_demotion_are_named_separately(registry):
    add_tech("alpha", "Alpha")
    add_tech("beta", "Beta")
    add_level("alpha", "L1", date(2026, 8, 1))
    add_level("beta", "L3", date(2026, 8, 1))
    build_digest.publish(build_digest.build(today=date(2026, 8, 1)))

    add_level("alpha", "L2", TODAY)
    add_level("beta", "L1", TODAY)
    issue = build_digest.build(today=TODAY)

    assert [i["name"] for i in issue.promoted] == ["Alpha"]
    assert [i["name"] for i in issue.demoted] == ["Beta"]
    assert "Поднялись" in issue.text
    assert "Понизились" in issue.text, "понижение называется прямо, а не умалчивается"


def test_issue_covers_only_the_period_since_the_previous_one(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", date(2026, 8, 1))
    build_digest.publish(build_digest.build(today=date(2026, 8, 1)))

    add_tech("beta", "Beta")
    add_level("beta", "L1", TODAY)
    issue = build_digest.build(today=TODAY)

    assert [i["name"] for i in issue.added] == ["Beta"], "прошлое не пересказывается"
    assert issue.since == date(2026, 8, 1)


def test_future_dated_entries_are_not_announced(registry):
    """Запись, датированная будущим, в сегодняшний выпуск не попадает."""
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", date(2026, 9, 1))
    issue = build_digest.build(today=TODAY)
    assert issue.added == []


# ─── Пустой выпуск ───────────────────────────────────────────────────────────


def test_no_news_means_no_issue(registry):
    """Полсотни сообщений «ничего не произошло» — это шум, а не дайджест."""
    add_tech("alpha", "Alpha")
    issue = build_digest.build(today=TODAY)

    assert not issue.has_news()
    assert issue.text == ""
    assert build_digest.run(today=TODAY) == 0
    assert build_digest.load_issues() == []


def test_quiet_period_after_a_loud_one_produces_nothing(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", date(2026, 8, 1))
    build_digest.publish(build_digest.build(today=date(2026, 8, 1)))

    build_digest.run(today=TODAY)
    assert len(build_digest.load_issues()) == 1


# ─── Выпуск не переписывается ────────────────────────────────────────────────


def test_published_issue_is_never_rewritten(registry):
    """Выпуск утверждает, что было верно в день выхода.

    Пересобрать его позже нельзя: по нынешним данным вышел бы другой текст, а
    прошлый читатель уже видел.
    """
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    first = build_digest.build(today=TODAY)
    build_digest.publish(first)

    add_tech("beta", "Beta")
    add_level("beta", "L1", TODAY)
    with pytest.raises(FileExistsError):
        build_digest.publish(build_digest.build(today=TODAY))


def test_second_run_on_the_same_day_is_harmless(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    assert build_digest.run(today=TODAY) == 0
    assert build_digest.run(today=TODAY) == 0
    assert len(build_digest.load_issues()) == 1


def test_dry_run_writes_nothing(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    build_digest.run(today=TODAY, dry_run=True)
    assert build_digest.load_issues() == []


# ─── Текст не утверждает лишнего ─────────────────────────────────────────────


def test_text_reports_the_state_it_reached(registry):
    add_tech("alpha", "Alpha")
    add_tech("silent", "Silent")
    add_level("alpha", "L2", TODAY)

    issue = build_digest.build(today=TODAY)

    assert issue.by_level == {"L2": 1, "unknown": 1}
    assert "L2 — 1" in issue.text
    assert "уровень не вычислен" in issue.text, (
        "запись без свидетельств не должна выглядеть как L0"
    )


def test_numbers_in_text_match_the_data(registry):
    for i in range(5):
        add_tech(f"t{i}", f"Tech {i}")
        add_level(f"t{i}", "L1", TODAY)
        add_evidence(f"t{i}", "publication", TODAY, f"https://arxiv.org/abs/{i}")

    issue = build_digest.build(today=TODAY)

    assert "5 записей" in issue.text
    assert "5 свидетельств" in issue.text
    assert issue.evidence_by_type == {"publication": 5}


def test_long_lists_are_cut_not_dumped(registry):
    for i in range(20):
        add_tech(f"t{i}", f"Tech {i}")
        add_level(f"t{i}", "L1", TODAY)

    issue = build_digest.build(today=TODAY)

    assert "Tech 0" in issue.text
    assert "Tech 19" not in issue.text, "выпуск — сообщение, а не выгрузка"
    assert "и ещё 12 записей" in issue.text


def test_broken_links_are_announced(registry):
    add_tech("alpha", "Alpha")
    store.append_run(store.CollectionRun(
        ran_at=TODAY, links_checked=40, links_broken=2,
    ))
    issue = build_digest.build(today=TODAY)

    assert issue.links_broken == 2
    assert "2 источника" in issue.text
    assert issue.has_news(), "исчезнувший источник — новость"


def test_issue_is_written_as_stable_json(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    path = build_digest.publish(build_digest.build(today=TODAY))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["issued_at"] == TODAY.isoformat()
    assert payload["text"]
    assert path.read_text(encoding="utf-8").endswith("\n")
