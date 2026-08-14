#!/usr/bin/env python3
"""A digest issue: what has changed since the previous one.

The portal knows what changed, and the only way to learn it is to visit the
portal. The digest carries the changes outward.

**No language model takes part.** There is nothing in a digest to invent: it
retells numbers already computed by a rule from collected evidence. That is
exactly why it is published without review by a person.

**An issue is data, not an artefact.** It asserts what was true on the day it
came out, and it cannot be rebuilt later: today's data would produce a different
text, and the reader has already seen the old one. Issues are therefore appended
to `data/digest/` and never rewritten, under the same discipline as the evidence
and the run log.

**An empty issue is not published.** A week without changes is an ordinary
thing, and fifty messages saying nothing happened would turn the digest into
noise. How recently the data was checked is visible from the run log anyway: it
answers whether anyone looked, and the digest answers what they found.

Usage::

    python3 scripts/build_digest.py            # publish, if there is anything to say
    python3 scripts/build_digest.py --dry-run  # show the text without writing
    python3 scripts/build_digest.py --force    # publish even without changes
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: The order of the levels, by which a promotion is told from a demotion. It is
#: the same order the artefact build uses, repeated here so that the digest does
#: not depend on it.
LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

DIGEST_DIR = store.DATA_DIR / "digest"

#: How many records to name outright. Beyond that a count: a list of forty names
#: goes unread, and the issue stops being a message and becomes a data dump.
NAMED_LIMIT = 8


def digest_dir() -> Path:
    """The directory of issues. Read afresh so that tests can substitute the root."""
    return store.DATA_DIR / "digest"


# ─── Russian numerals ────────────────────────────────────────────────────────
#
# Russian agrees a noun with the number before it in three forms. The rule is
# simple, but an error in it shows at once and spoils trust in the rest of the
# text: a reader who sees the wrong form doubts the numbers too, and rightly.


def plural(count: int, one: str, few: str, many: str) -> str:
    """The Russian form of a word for a given count."""
    tail_100 = abs(count) % 100
    tail_10 = abs(count) % 10
    if 11 <= tail_100 <= 14:
        return many
    if tail_10 == 1:
        return one
    if 2 <= tail_10 <= 4:
        return few
    return many


def counted(count: int, one: str, few: str, many: str) -> str:
    return f"{count} {plural(count, one, few, many)}"


# ─── An issue ────────────────────────────────────────────────────────────────


@dataclass
class Issue:
    """One issue: what happened over the period and how it is told."""

    issued_at: date
    #: The start of the period: the date of the previous issue. It is shown to
    #: the reader but does not bound the period — see the marks below.
    since: date | None
    #: How many journal entries the previous issues already covered.
    #:
    #: A boundary by date loses data: a change that happened on the day of an
    #: issue but after it reaches neither this issue nor the next — it falls
    #: between them for ever. The journals are appended to and never rewritten,
    #: so the count of entries already covered is an exact and stable mark,
    #: whereas a date is not.
    levels_seen: int = 0
    evidence_seen: int = 0
    runs_seen: int = 0
    added: list[dict] = field(default_factory=list)
    promoted: list[dict] = field(default_factory=list)
    demoted: list[dict] = field(default_factory=list)
    evidence_added: int = 0
    evidence_by_type: dict[str, int] = field(default_factory=dict)
    links_checked: int = 0
    links_broken: int = 0
    #: The distribution by level on the day of the issue, so that the reader
    #: sees not only the change but the state it led to.
    by_level: dict[str, int] = field(default_factory=dict)
    total: int = 0
    #: The text of the issue in each language of the portal. An issue is never
    #: rewritten, so both texts are born at once: a translation cannot be added
    #: to an issue already out, and showing an English reader a Russian paragraph
    #: is the same as showing them a broken page.
    text: str = ""
    text_en: str = ""

    def has_news(self) -> bool:
        return bool(
            self.added or self.promoted or self.demoted
            or self.evidence_added or self.links_broken
        )

    def to_json(self) -> dict:
        payload = {
            "issued_at": self.issued_at.isoformat(),
            "since": self.since.isoformat() if self.since else None,
            "levels_seen": self.levels_seen,
            "evidence_seen": self.evidence_seen,
            "runs_seen": self.runs_seen,
            "added": self.added,
            "promoted": self.promoted,
            "demoted": self.demoted,
            "evidence_added": self.evidence_added,
            "evidence_by_type": self.evidence_by_type,
            "links_checked": self.links_checked,
            "links_broken": self.links_broken,
            "by_level": self.by_level,
            "total": self.total,
            "text": self.text,
            "text_en": self.text_en,
        }
        return payload


def load_issues() -> list[dict]:
    """The issues already published, oldest first."""
    directory = digest_dir()
    if not directory.exists():
        return []
    issues = []
    for path in sorted(directory.glob("*.json")):
        issues.append(json.loads(path.read_text(encoding="utf-8")))
    return sorted(issues, key=lambda i: i["issued_at"])


def latest_issue() -> dict | None:
    issues = load_issues()
    return issues[-1] if issues else None


def _names(technologies: list[store.Technology]) -> dict[str, str]:
    return {t.id: t.name for t in technologies}


def _listing(items: list[dict]) -> str:
    """Names separated by commas, cut off at a reasonable number."""
    names = [item["name"] for item in items]
    if len(names) <= NAMED_LIMIT:
        return ", ".join(names)
    shown = ", ".join(names[:NAMED_LIMIT])
    rest = len(names) - NAMED_LIMIT
    return f"{shown} и ещё {counted(rest, 'запись', 'записи', 'записей')}"


def compose(issue: Issue) -> str:
    """The text of an issue, from a template. Nothing beyond what is computed.

    Relations are named by words rather than by dashes. A dash hides the
    relation between parts of a phrase, and the reader has to work out for
    themselves whether it is a list, a cause or a qualification. The text is
    generated from a template and published without review by a person, so it
    must not force anyone to guess.
    """
    parts: list[str] = []

    if issue.added:
        parts.append(
            f"Впервые получили уровень "
            f"{counted(len(issue.added), 'запись', 'записи', 'записей')}: "
            f"{_listing(issue.added)}."
        )
    if issue.promoted:
        moves = ", ".join(
            f"{item['name']} с {item['level_before']} до {item['level_after']}"
            for item in issue.promoted[:NAMED_LIMIT]
        )
        tail = ""
        if len(issue.promoted) > NAMED_LIMIT:
            rest = len(issue.promoted) - NAMED_LIMIT
            tail = f", а также ещё {counted(rest, 'запись', 'записи', 'записей')}"
        parts.append(f"Поднялись в уровне {moves}{tail}.")
    if issue.demoted:
        moves = ", ".join(
            f"{item['name']} с {item['level_before']} до {item['level_after']}"
            for item in issue.demoted
        )
        # A demotion is named outright: evidence that turned out weaker than
        # it was thought is as much news as a confirmation.
        parts.append(f"Опустились в уровне {moves}.")

    if issue.evidence_added:
        kinds = ", ".join(
            f"{count} {EVIDENCE_NAMES.get(kind, kind)}"
            for kind, count in sorted(
                issue.evidence_by_type.items(), key=lambda kv: (-kv[1], kv[0])
            )
        )
        amount = counted(
            issue.evidence_added, "свидетельство", "свидетельства", "свидетельств"
        )
        parts.append(f"Собрано {amount}" + (f": {kinds}." if kinds else "."))

    if issue.links_broken:
        parts.append(
            "Перестали открываться "
            f"{counted(issue.links_broken, 'источник', 'источника', 'источников')}, "
            "и эти записи ждут правки."
        )

    if issue.by_level:
        # The noun goes with the first number and the rest imply it: "L0 on 7
        # records, L1 on 17" reads, while repeating the word in every member of
        # the list does not.
        pairs = [
            (level, count)
            for level, count in sorted(issue.by_level.items())
            if level != "unknown"
        ]
        known = [
            f"{level} у {counted(count, 'записи', 'записей', 'записей')}"
            if index == 0 else f"{level} у {count}"
            for index, (level, count) in enumerate(pairs)
        ]
        unknown = issue.by_level.get("unknown", 0)
        state = (
            f"Сейчас в реестре "
            f"{counted(issue.total, 'запись', 'записи', 'записей')}. "
            f"Уровень {', '.join(known)}"
        )
        if unknown:
            state += (
                f". У {counted(unknown, 'записи', 'записей', 'записей')} уровень "
                "не вычислен, потому что свидетельств пока нет"
            )
        parts.append(state + ".")

    return " ".join(parts)


def _listing_en(items: list[dict]) -> str:
    names = [item["name"] for item in items]
    if len(names) <= NAMED_LIMIT:
        return ", ".join(names)
    rest = len(names) - NAMED_LIMIT
    return ", ".join(names[:NAMED_LIMIT]) + f" and {rest} more"


def compose_en(issue: Issue) -> str:
    """The same issue in English.

    A separate writer rather than a translation of a finished string: the Russian
    text declines its nouns after numbers, and translating it word by word would
    carry a foreign grammar into English.
    """
    def plural_en(count: int, one: str, many: str) -> str:
        return f"{count} {one if count == 1 else many}"

    parts: list[str] = []

    if issue.added:
        parts.append(
            f"Received a level for the first time: "
            f"{plural_en(len(issue.added), 'record', 'records')}, "
            f"namely {_listing_en(issue.added)}."
        )
    if issue.promoted:
        moves = ", ".join(
            f"{item['name']} from {item['level_before']} to {item['level_after']}"
            for item in issue.promoted[:NAMED_LIMIT]
        )
        tail = ""
        if len(issue.promoted) > NAMED_LIMIT:
            rest = len(issue.promoted) - NAMED_LIMIT
            tail = f", plus {plural_en(rest, 'record', 'records')}"
        parts.append(f"Rose in level: {moves}{tail}.")
    if issue.demoted:
        moves = ", ".join(
            f"{item['name']} from {item['level_before']} to {item['level_after']}"
            for item in issue.demoted
        )
        parts.append(f"Fell in level: {moves}.")

    if issue.evidence_added:
        kinds = ", ".join(
            f"{count} {EVIDENCE_NAMES_EN.get(kind, kind)}"
            for kind, count in sorted(
                issue.evidence_by_type.items(), key=lambda kv: (-kv[1], kv[0])
            )
        )
        amount = plural_en(issue.evidence_added, "piece of evidence", "pieces of evidence")
        parts.append(f"Collected {amount}" + (f": {kinds}." if kinds else "."))

    if issue.links_broken:
        parts.append(
            f"{plural_en(issue.links_broken, 'source', 'sources')} stopped resolving, "
            "and those records await a fix."
        )

    if issue.by_level:
        pairs = [
            (level, count) for level, count in sorted(issue.by_level.items())
            if level != "unknown"
        ]
        known = [
            f"{level} in {plural_en(count, 'record', 'records')}"
            if index == 0 else f"{level} in {count}"
            for index, (level, count) in enumerate(pairs)
        ]
        unknown = issue.by_level.get("unknown", 0)
        state = (
            f"The registry now holds {plural_en(issue.total, 'record', 'records')}. "
            f"Level {', '.join(known)}"
        )
        if unknown:
            state += (
                f". For {plural_en(unknown, 'record', 'records')} no level is computed, "
                "because there is no evidence yet"
            )
        parts.append(state + ".")

    return " ".join(parts)


#: The names of the evidence kinds as a reader sees them, in English.
EVIDENCE_NAMES_EN = {
    "publication": "about publications",
    "independent_reproduction": "about independent reproductions",
    "repository": "about repositories",
    "build_run": "about builds",
    "framework_presence": "about presence in frameworks",
    "package_downloads": "about package downloads",
    "industrial_use": "about industrial use",
    "provider_count": "about providers",
}

#: The names of the evidence kinds as a reader sees them, in Russian. The keys
#: are the values of `EvidenceType`.
EVIDENCE_NAMES = {
    "publication": "о публикациях",
    "independent_reproduction": "о независимых воспроизведениях",
    "repository": "о репозиториях",
    "build_run": "о сборках",
    "framework_presence": "о присутствии во фреймворках",
    "package_downloads": "о загрузках пакетов",
    "industrial_use": "о промышленном применении",
    "provider_count": "о поставщиках",
}


def build(*, today: date | None = None, force: bool = False) -> Issue:
    """Build the issue covering the period from the previous one to today."""
    today = today or date.today()
    previous = latest_issue()
    since = date.fromisoformat(previous["issued_at"]) if previous else None

    # The marks of the previous issue: how many journal entries it covered.
    levels_seen = int(previous.get("levels_seen", 0)) if previous else 0
    evidence_seen = int(previous.get("evidence_seen", 0)) if previous else 0
    runs_seen = int(previous.get("runs_seen", 0)) if previous else 0

    technologies = store.load_technologies()
    names = _names(technologies)
    order = {level: i for i, level in enumerate(LEVELS)}

    issue = Issue(issued_at=today, since=since)

    # Level changes: the journal is read whole, because whether a level appears
    # for the first time is decided by the history and not by a single line.
    # What counts as covered is what the previous issue already counted.
    all_levels = store.load_levels()
    issue.levels_seen = len(all_levels)
    seen: dict[str, str] = {}
    for index, entry in enumerate(all_levels):
        before = seen.get(entry.technology_id)
        seen[entry.technology_id] = entry.level
        if index < levels_seen:
            continue
        if entry.computed_at > today:
            continue
        item = {
            "technology_id": entry.technology_id,
            "name": names.get(entry.technology_id, entry.technology_id),
            "level_before": before,
            "level_after": entry.level,
        }
        if before is None:
            issue.added.append(item)
        elif order.get(entry.level, 0) > order.get(before, 0):
            issue.promoted.append(item)
        else:
            issue.demoted.append(item)

    # The evidence of the period.
    all_evidence = store.load_evidence()
    issue.evidence_seen = len(all_evidence)
    fresh = [e for e in all_evidence[evidence_seen:] if e.fetched_at <= today]
    issue.evidence_added = len(fresh)
    issue.evidence_by_type = dict(sorted(Counter(e.type for e in fresh).items()))

    # The link check over the period, taken from the run log.
    all_runs = store.load_runs()
    issue.runs_seen = len(all_runs)
    for index, run in enumerate(all_runs):
        if index < runs_seen:
            continue
        if run.ran_at > today:
            continue
        issue.links_checked += run.links_checked
        issue.links_broken += run.links_broken

    # The state on the day of the issue.
    issue.total = len(technologies)
    issue.by_level = dict(sorted(Counter(
        (store.latest_level(t.id).level if store.latest_level(t.id) else "unknown")
        for t in technologies
    ).items()))

    if issue.has_news() or force:
        issue.text = compose(issue)
        issue.text_en = compose_en(issue)
    return issue


def publish(issue: Issue) -> Path:
    """Write the issue. An existing file is never overwritten."""
    directory = digest_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{issue.issued_at.isoformat()}.json"
    if path.exists():
        raise FileExistsError(
            f"the issue for {issue.issued_at} already exists: {path}. An issue "
            "asserts what was true on the day it came out, and it must not be "
            "rewritten."
        )
    path.write_text(
        json.dumps(issue.to_json(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run(*, today: date | None = None, dry_run: bool = False, force: bool = False) -> int:
    issue = build(today=today, force=force)

    if not issue.has_news() and not force:
        print("no issue built: nothing has changed since the previous one")
        return 0

    print(issue.text)
    if dry_run:
        return 0

    path = digest_dir() / f"{issue.issued_at.isoformat()}.json"
    if path.exists():
        print(f"the issue for {issue.issued_at} already exists, no second one")
        return 0

    print(f"\nthe issue is written: {publish(issue)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show without writing")
    parser.add_argument(
        "--force", action="store_true",
        help="publish even when nothing changed",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
