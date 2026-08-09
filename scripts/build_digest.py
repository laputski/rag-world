#!/usr/bin/env python3
"""Выпуск дайджеста: что изменилось со времени прошлого выпуска.

Портал знает, что изменилось, но узнать об этом можно, только зайдя на него.
Дайджест выносит изменения наружу.

**Языковая модель здесь не участвует.** Выдумать в дайджесте нечего: он
пересказывает числа, которые уже вычислены правилом из собранных свидетельств.
Ровно поэтому он публикуется сам, без просмотра человеком, тогда как аннотации
записей — жанр, где модель порождает правдоподобное, а не проверенное, — просмотр
проходят обязательно (STAGE-news-generator.md, разделение жанров по допуску).

**Выпуск — данные, а не артефакт.** Он утверждает, что было верно в день его
выхода, и пересобрать его позже нельзя: по нынешним данным получился бы другой
текст, а прошлый выпуск читатель уже видел. Поэтому выпуски дозаписываются в
`data/digest/` и никогда не переписываются — та же дисциплина, что у
свидетельств и журнала прогонов.

**Пустой выпуск не выходит.** Неделя без изменений — обычное дело, и полсотни
сообщений «ничего не произошло» превратили бы дайджест в шум. Свежесть проверки
и без того видна по журналу прогонов: он отвечает на вопрос «смотрели ли», а
дайджест — на вопрос «что нашли».

Использование::

    python3 scripts/build_digest.py            # выпустить, если есть о чём
    python3 scripts/build_digest.py --dry-run  # показать текст, не записывая
    python3 scripts/build_digest.py --force    # выпустить даже без изменений
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

#: Порядок уровней: по нему отличается повышение от понижения. Тот же, что в
#: сборке артефактов; здесь повторён, чтобы дайджест не зависел от неё.
LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

DIGEST_DIR = store.DATA_DIR / "digest"

#: Сколько записей перечислять поимённо. Дальше — числом: список из сорока имён
#: читатель не прочитает, а выпуск перестанет быть сообщением и станет выгрузкой.
NAMED_LIMIT = 8


def digest_dir() -> Path:
    """Каталог выпусков. Читается заново, чтобы тесты могли подменить корень."""
    return store.DATA_DIR / "digest"


# ─── Русские числительные ────────────────────────────────────────────────────
#
# «1 запись», «2 записи», «5 записей» — правило простое, но ошибка в нём видна
# сразу и портит доверие к остальному тексту: читатель, увидевший «5 запись»,
# справедливо усомнится и в числах.


def plural(count: int, one: str, few: str, many: str) -> str:
    """Форма слова при числе по правилам русского языка."""
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


# ─── Выпуск ──────────────────────────────────────────────────────────────────


@dataclass
class Issue:
    """Один выпуск: что произошло за период и как об этом сказано."""

    issued_at: date
    #: Начало периода: дата прошлого выпуска. Показывается читателю, но границу
    #: периода не задаёт — см. отметки ниже.
    since: date | None
    #: Сколько записей журналов уже охвачено прошлыми выпусками.
    #:
    #: Граница по дате теряет данные: изменение, случившееся в день выпуска, но
    #: после него, не попадает ни в этот выпуск, ни в следующий — оно
    #: проваливается между ними навсегда. Журналы дописываются и не
    #: переписываются, поэтому число уже охваченных записей — точная и
    #: устойчивая отметка, а дата — нет.
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
    #: Распределение по уровням на день выпуска — чтобы читатель видел не только
    #: изменение, но и состояние, к которому оно привело.
    by_level: dict[str, int] = field(default_factory=dict)
    total: int = 0
    text: str = ""

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
        }
        return payload


def load_issues() -> list[dict]:
    """Выпущенные дайджесты, от старых к новым."""
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
    """Имена через запятую, с обрывом на разумном числе."""
    names = [item["name"] for item in items]
    if len(names) <= NAMED_LIMIT:
        return ", ".join(names)
    shown = ", ".join(names[:NAMED_LIMIT])
    rest = len(names) - NAMED_LIMIT
    return f"{shown} и ещё {counted(rest, 'запись', 'записи', 'записей')}"


def compose(issue: Issue) -> str:
    """Текст выпуска по шаблону. Ничего, кроме уже вычисленного."""
    parts: list[str] = []

    if issue.added:
        parts.append(
            f"Впервые получили уровень {_listing(issue.added)} — "
            f"{counted(len(issue.added), 'запись', 'записи', 'записей')}."
        )
    if issue.promoted:
        moves = ", ".join(
            f"{item['name']} ({item['level_before']} → {item['level_after']})"
            for item in issue.promoted[:NAMED_LIMIT]
        )
        tail = ""
        if len(issue.promoted) > NAMED_LIMIT:
            rest = len(issue.promoted) - NAMED_LIMIT
            tail = f" и ещё {counted(rest, 'запись', 'записи', 'записей')}"
        parts.append(f"Поднялись в уровне: {moves}{tail}.")
    if issue.demoted:
        moves = ", ".join(
            f"{item['name']} ({item['level_before']} → {item['level_after']})"
            for item in issue.demoted
        )
        # Понижение называется прямо: свидетельство, оказавшееся слабее, чем
        # считалось, — такая же новость, как и подтверждение.
        parts.append(f"Понизились: {moves}.")

    if issue.evidence_added:
        kinds = ", ".join(
            f"{EVIDENCE_NAMES.get(kind, kind)} — {count}"
            for kind, count in sorted(
                issue.evidence_by_type.items(), key=lambda kv: (-kv[1], kv[0])
            )
        )
        amount = counted(
            issue.evidence_added, "свидетельство", "свидетельства", "свидетельств"
        )
        parts.append(f"Добавлено {amount}" + (f" ({kinds})." if kinds else "."))

    if issue.links_broken:
        parts.append(
            f"Перестали открываться "
            f"{counted(issue.links_broken, 'источник', 'источника', 'источников')} — "
            "записи ждут правки."
        )

    if issue.by_level:
        spread = ", ".join(
            f"{level} — {count}"
            for level, count in sorted(issue.by_level.items())
            if level != "unknown"
        )
        unknown = issue.by_level.get("unknown", 0)
        state = f"Сейчас в реестре {counted(issue.total, 'запись', 'записи', 'записей')}: {spread}"
        if unknown:
            state += (
                f"; у {counted(unknown, 'записи', 'записей', 'записей')} "
                "уровень не вычислен — свидетельств пока нет"
            )
        parts.append(state + ".")

    return " ".join(parts)


#: Названия видов свидетельств для читателя. Ключи — значения `EvidenceType`.
EVIDENCE_NAMES = {
    "publication": "публикации",
    "independent_reproduction": "независимые воспроизведения",
    "repository": "репозитории",
    "build_run": "сборки",
    "framework_presence": "присутствие во фреймворках",
    "package_downloads": "загрузки пакетов",
    "industrial_use": "промышленное применение",
    "provider_count": "поставщики",
}


def build(*, today: date | None = None, force: bool = False) -> Issue:
    """Собрать выпуск за период с прошлого выпуска по сегодня."""
    today = today or date.today()
    previous = latest_issue()
    since = date.fromisoformat(previous["issued_at"]) if previous else None

    # Отметки прошлого выпуска: сколько записей журналов он уже охватил.
    levels_seen = int(previous.get("levels_seen", 0)) if previous else 0
    evidence_seen = int(previous.get("evidence_seen", 0)) if previous else 0
    runs_seen = int(previous.get("runs_seen", 0)) if previous else 0

    technologies = store.load_technologies()
    names = _names(technologies)
    order = {level: i for i, level in enumerate(LEVELS)}

    issue = Issue(issued_at=today, since=since)

    # Изменения уровней: журнал читается целиком, потому что «первое появление»
    # определяется историей, а не одной строкой. Охваченным считается то, что
    # уже сосчитано прошлым выпуском.
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

    # Свидетельства за период.
    all_evidence = store.load_evidence()
    issue.evidence_seen = len(all_evidence)
    fresh = [e for e in all_evidence[evidence_seen:] if e.fetched_at <= today]
    issue.evidence_added = len(fresh)
    issue.evidence_by_type = dict(sorted(Counter(e.type for e in fresh).items()))

    # Проверка ссылок за период — из журнала прогонов.
    all_runs = store.load_runs()
    issue.runs_seen = len(all_runs)
    for index, run in enumerate(all_runs):
        if index < runs_seen:
            continue
        if run.ran_at > today:
            continue
        issue.links_checked += run.links_checked
        issue.links_broken += run.links_broken

    # Состояние на день выпуска.
    issue.total = len(technologies)
    issue.by_level = dict(sorted(Counter(
        (store.latest_level(t.id).level if store.latest_level(t.id) else "unknown")
        for t in technologies
    ).items()))

    issue.text = compose(issue) if (issue.has_news() or force) else ""
    return issue


def publish(issue: Issue) -> Path:
    """Записать выпуск. Существующий файл не переписывается никогда."""
    directory = digest_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{issue.issued_at.isoformat()}.json"
    if path.exists():
        raise FileExistsError(
            f"выпуск за {issue.issued_at} уже существует: {path}. "
            "Выпуск утверждает, что было верно в день выхода, и переписывать "
            "его нельзя."
        )
    path.write_text(
        json.dumps(issue.to_json(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run(*, today: date | None = None, dry_run: bool = False, force: bool = False) -> int:
    issue = build(today=today, force=force)

    if not issue.has_news() and not force:
        print("выпуск не собран: со времени прошлого ничего не изменилось")
        return 0

    print(issue.text)
    if dry_run:
        return 0

    path = digest_dir() / f"{issue.issued_at.isoformat()}.json"
    if path.exists():
        print(f"выпуск за {issue.issued_at} уже существует, повторный не пишется")
        return 0

    print(f"\nвыпуск записан: {publish(issue)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="показать, не записывая")
    parser.add_argument(
        "--force", action="store_true",
        help="выпустить даже когда изменений нет",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
