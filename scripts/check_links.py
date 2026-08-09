#!/usr/bin/env python3
"""Проверка разрешимости ссылок реестра.

Ссылка — единственное, чем запись отличается от упоминания: без разрешимого
источника имя технологии ничего не подтверждает. Проверка входит в
еженедельный прогон, потому что ссылки гниют молча — площадка переезжает,
препринт снимают, репозиторий переименовывают, и запись продолжает выглядеть
обоснованной.

Различаются три исхода, и различие существенно:

* **разрешается** — отметка `verified` с датой; читатель видит, что ссылку
  открывали, а не просто вписали;
* **не существует** — 404 либо 410, отметка `unresolved`: адрес указывает в
  пустоту, и это надо чинить руками;
* **непонятно** — отказ по правам, ограничение частоты, ошибка сети, отказ
  сервера. Отметка не меняется вовсе.

Последнее правило — главное. Временный отказ не должен превращать проверенную
ссылку в несуществующую: издательства отвечают отказом роботам, сеть рвётся, а
запись после этого выглядела бы испорченной, хотя с ней всё в порядке.

Перечень разрешённых доменов здесь снят намеренно: он ограждает сбор
свидетельств от блуждания по адресам из содержимого источников, а ссылки
реестра вписаны нами, и многие ведут на площадки, которых в перечне нет.

Использование::

    python3 scripts/check_links.py              # проверить и проставить отметки
    python3 scripts/check_links.py --dry-run    # только показать, что изменится
    python3 scripts/check_links.py --stale 30   # только не проверявшиеся 30 дней
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: Коды, означающие, что адреса не существует. Всё прочее — не приговор.
GONE = (404, 410)

#: Коды, означающие «есть, но не показывает»: права, оплата, защита от роботов.
GUARDED = (401, 402, 403, 429)


@dataclass
class LinkSummary:
    """Итог прохода по ссылкам."""

    checked: int = 0
    verified: int = 0
    gone: int = 0
    guarded: int = 0
    errored: int = 0
    changed: int = 0
    problems: list[str] = field(default_factory=list)


def _outcome(status: int) -> str:
    if 200 <= status < 400:
        return "verified"
    if status in GONE:
        return "unresolved"
    return "unknown"


def run(
    *,
    http=None,
    today: date | None = None,
    dry_run: bool = False,
    stale_after: int = 0,
) -> LinkSummary:
    """Обойти ссылки реестра и обновить их отметки.

    `stale_after` в днях позволяет не перепроверять недавно подтверждённые
    ссылки: за неделю адрес, открывавшийся вчера, обычно не исчезает, а лишние
    обращения — расход чужих ресурсов и своего времени.
    """
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport(allow_any_host=True)
    today = today or date.today()
    summary = LinkSummary()

    # Один адрес проверяется один раз, даже если встречается у нескольких
    # записей: результат от записи не зависит.
    outcomes: dict[str, tuple[str, int]] = {}

    for tech in store.load_technologies():
        touched = False
        for link in tech.links:
            if not link.url.strip():
                continue
            if (
                stale_after
                and link.status == "verified"
                and link.verified_at is not None
                and today - link.verified_at < timedelta(days=stale_after)
            ):
                continue

            if link.url not in outcomes:
                summary.checked += 1
                try:
                    status, _ = http.get(link.url, timeout=20)
                except Exception as exc:  # сеть рвётся — это не приговор ссылке
                    outcomes[link.url] = ("unknown", 0)
                    summary.problems.append(f"{tech.id}: {link.url} — {exc}"[:160])
                else:
                    outcomes[link.url] = (_outcome(status), status)

            verdict, status = outcomes[link.url]
            if verdict == "verified":
                summary.verified += 1
                if link.status != "verified" or link.verified_at != today:
                    link.status = "verified"
                    link.verified_at = today
                    touched = True
            elif verdict == "unresolved":
                summary.gone += 1
                summary.problems.append(
                    f"{tech.id}: {link.url} отвечает кодом {status}"
                )
                if link.status != "unresolved":
                    link.status = "unresolved"
                    link.verified_at = None
                    touched = True
            else:
                # Отметка не трогается: временный отказ не портит запись.
                if status in GUARDED:
                    summary.guarded += 1
                else:
                    summary.errored += 1
                if status:
                    summary.problems.append(
                        f"{tech.id}: {link.url} отвечает кодом {status} "
                        "(отметка не изменена)"
                    )

        if touched and not dry_run:
            store.save_technology(tech)
            summary.changed += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="ничего не записывать")
    parser.add_argument(
        "--stale", type=int, default=0,
        help="не перепроверять ссылки, подтверждённые за последние N дней",
    )
    args = parser.parse_args()

    summary = run(dry_run=args.dry_run, stale_after=args.stale)
    print(
        f"проверено адресов {summary.checked}: "
        f"разрешается {summary.verified}, не существует {summary.gone}, "
        f"закрыто правами {summary.guarded}, ошибок обращения {summary.errored}"
    )
    print(f"записей изменено: {summary.changed}")
    for problem in summary.problems:
        print(f"  {problem}")
    return 1 if summary.gone else 0


if __name__ == "__main__":
    raise SystemExit(main())
