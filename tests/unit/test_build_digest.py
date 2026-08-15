"""The digest retells what was computed rather than talking about it.

An issue is published without review by a person, so the only thing keeping it
from untruth is that there is nothing invented in it. What is checked here is
that an issue claims no more than the data holds, does not go out empty, and is
never rewritten after the fact.

The Russian numerals are checked separately: a wrong plural form undermines trust
in the whole text, the correct numbers included.
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


# ─── Russian numerals ────────────────────────────────────────────────────────


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


# ─── What goes into an issue ─────────────────────────────────────────────────


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
    assert "Поднялись в уровне Alpha с L1 до L2" in issue.text
    assert "Опустились в уровне Beta с L3 до L1" in issue.text, (
        "a demotion is named outright rather than passed over"
    )
    assert "—" not in issue.text, "relations are named by words, not by dashes"


def test_issue_covers_only_the_period_since_the_previous_one(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", date(2026, 8, 1))
    build_digest.publish(build_digest.build(today=date(2026, 8, 1)))

    add_tech("beta", "Beta")
    add_level("beta", "L1", TODAY)
    issue = build_digest.build(today=TODAY)

    assert [i["name"] for i in issue.added] == ["Beta"], "the past is not retold"
    assert issue.since == date(2026, 8, 1)


def test_future_dated_entries_are_not_announced(registry):
    """A record dated in the future does not enter today's issue."""
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", date(2026, 9, 1))
    issue = build_digest.build(today=TODAY)
    assert issue.added == []


# ─── An empty issue ──────────────────────────────────────────────────────────


def test_no_news_means_no_issue(registry):
    """Fifty messages saying nothing happened are noise, not a digest."""
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


# ─── An issue is never rewritten ─────────────────────────────────────────────


def test_published_issue_is_never_rewritten(registry):
    """An issue asserts what was true on the day it came out.

    It cannot be rebuilt later: today's data would produce a different text, and
    the reader has already seen the old one.
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


# ─── The text claims nothing extra ───────────────────────────────────────────


def test_text_reports_the_state_it_reached(registry):
    add_tech("alpha", "Alpha")
    add_tech("silent", "Silent")
    add_level("alpha", "L2", TODAY)

    issue = build_digest.build(today=TODAY)

    assert issue.by_level == {"L2": 1, "unknown": 1}
    assert "Уровень L2 у 1 записи" in issue.text
    assert "уровень не вычислен, потому что свидетельств пока нет" in issue.text, (
        "a record with no evidence must not look like L0"
    )


def test_numbers_in_text_match_the_data(registry):
    for i in range(5):
        add_tech(f"t{i}", f"Tech {i}")
        add_level(f"t{i}", "L1", TODAY)
        add_evidence(f"t{i}", "publication", TODAY, f"https://arxiv.org/abs/{i}")

    issue = build_digest.build(today=TODAY)

    assert "5 записей" in issue.text
    assert "Собрано 5 свидетельств" in issue.text
    assert issue.evidence_by_type == {"publication": 5}


def test_long_lists_are_cut_not_dumped(registry):
    for i in range(20):
        add_tech(f"t{i}", f"Tech {i}")
        add_level(f"t{i}", "L1", TODAY)

    issue = build_digest.build(today=TODAY)

    assert "Tech 0" in issue.text
    assert "Tech 19" not in issue.text, "an issue is a message, not a data dump"
    assert "и ещё 12 записей" in issue.text


def test_broken_links_are_announced(registry):
    add_tech("alpha", "Alpha")
    store.append_run(store.CollectionRun(
        ran_at=TODAY, links_checked=40, links_broken=2,
    ))
    issue = build_digest.build(today=TODAY)

    assert issue.links_broken == 2
    assert "2 источника" in issue.text
    assert issue.has_news(), "a vanished source is news"


def test_issue_is_written_as_stable_json(registry):
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    path = build_digest.publish(build_digest.build(today=TODAY))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["issued_at"] == TODAY.isoformat()
    assert payload["text"]
    assert path.read_text(encoding="utf-8").endswith("\n")


# ─── The boundary of the period ──────────────────────────────────────────────


def test_changes_after_an_issue_on_the_same_day_are_not_lost(registry):
    """A change that happened on the day of an issue but after it.

    A boundary by date lost such changes for ever: they did not enter this issue
    because it had already gone out, nor the next one because their date was not
    later than the previous issue's. The failure was silent: the portal showed
    the new state and the digest never reported it.

    The mark is set by the number of journal entries rather than by a date: the
    journals are appended to and never rewritten, so the count of what is covered
    is exact.
    """
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    build_digest.publish(build_digest.build(today=TODAY))

    # The same day but after the issue: the pass found a promotion and evidence.
    add_level("alpha", "L2", TODAY)
    add_evidence("alpha", "repository", TODAY, "https://github.com/x/y")

    issue = build_digest.build(today=TODAY)

    assert [i["name"] for i in issue.promoted] == ["Alpha"]
    assert issue.evidence_added == 1
    assert issue.has_news(), "changes on the day of an issue must reach the next one"


def test_watermarks_advance_with_each_issue(registry):
    """Every issue records how much of the journals it covered."""
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    add_evidence("alpha", "publication", TODAY, "https://arxiv.org/abs/1")
    first = build_digest.build(today=TODAY)

    assert first.levels_seen == 1
    assert first.evidence_seen == 1
    build_digest.publish(first)

    add_level("alpha", "L2", TODAY)
    second = build_digest.build(today=TODAY)
    assert second.levels_seen == 2
    assert len(second.promoted) == 1


def test_nothing_is_reported_twice(registry):
    """What the previous issue covered is not retold by the next one."""
    add_tech("alpha", "Alpha")
    add_level("alpha", "L1", TODAY)
    add_evidence("alpha", "publication", TODAY, "https://arxiv.org/abs/1")
    build_digest.publish(build_digest.build(today=TODAY))

    again = build_digest.build(today=TODAY)
    assert not again.has_news()
    assert again.added == []
    assert again.evidence_added == 0


def test_text_uses_words_instead_of_dashes(registry):
    """A dash hides the relation between parts of a phrase.

    The reader has to work out for themselves whether it is a list, a cause or a
    qualification. The text is generated from a template and goes out without
    review, so it must not make anyone guess.
    """
    for i in range(3):
        add_tech(f"t{i}", f"Tech {i}")
        add_level(f"t{i}", "L1", TODAY)
        add_evidence(f"t{i}", "publication", TODAY, f"https://arxiv.org/abs/{i}")

    text = build_digest.build(today=TODAY).text

    assert "—" not in text, f"an em dash instead of a verb: {text}"
    assert "→" not in text, f"an arrow instead of words: {text}"
    assert "с L" not in text or "до L" in text, "a level transition is named in words"
