#!/usr/bin/env python3
"""Check that the registry's links resolve.

A link is the only thing separating a record from a mention: without a
resolvable source, the name of a technology confirms nothing. The check runs in
the weekly pass because links rot in silence — a venue moves, a preprint is
withdrawn, a repository is renamed, and the record goes on looking grounded.

Three outcomes are distinguished, and the distinction matters:

* **it resolves** — the mark becomes `verified` with a date, so a reader sees
  that the link was opened rather than merely written down;
* **it does not exist** — a 404 or a 410 gives the mark `unresolved`: the
  address points into nothing, and that has to be repaired by hand;
* **it is unclear** — a refusal on rights, a rate limit, a network error, a
  server failure. The mark does not change at all.

The last rule is the important one. A temporary refusal must not turn a verified
link into a non-existent one: publishers refuse robots and networks break, and
the record would then look damaged while nothing is wrong with it.

The allowlist of hosts is deliberately lifted here. It guards evidence
collection from wandering to addresses met in the content of sources, whereas
the registry's links were written by us and many of them lead to venues the list
does not contain.

Usage::

    python3 scripts/check_links.py              # check and set the marks
    python3 scripts/check_links.py --dry-run    # show what would change
    python3 scripts/check_links.py --stale 30   # only those unchecked for 30 days
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
    if status in GUARDED:
        return "guarded"
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
            # Недавно осмотренные адреса пропускаются. Закрытые правами тоже:
            # площадка, отказавшая роботу вчера, откажет и сегодня, а лишнее
            # обращение — расход чужих ресурсов ради заведомо известного ответа.
            if (
                stale_after
                and link.status in ("verified", "guarded")
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
            elif verdict == "guarded":
                # Отказ по правам не понижает подтверждённую ссылку: издательства
                # отвечают так роботам, и принять это за смерть адреса значит
                # испортить реестр быстрее, чем время испортит адреса.
                #
                # Но и оставлять непроверенную ссылку в прежнем состоянии
                # нельзя. Она застревала в «не смотрели» навсегда, хотя
                # смотрели каждую неделю, и отличить её от действительно не
                # проверявшейся было невозможно. Отметка `guarded` утверждает
                # ровно наблюдённое: обращение было, адрес ответил, роботу себя
                # не показал. Подтвердить его может только человек.
                summary.guarded += 1
                if link.status == "verified":
                    summary.problems.append(
                        f"{tech.id}: {link.url} отвечает кодом {status} "
                        "(отметка о проверке сохранена)"
                    )
                elif link.status != "guarded" or link.verified_at != today:
                    link.status = "guarded"
                    link.verified_at = today
                    touched = True
                    summary.problems.append(
                        f"{tech.id}: {link.url} отвечает кодом {status}, "
                        "подтвердить может только человек"
                    )
            else:
                # Обрыв связи, таймаут, неизвестный код: отметка не трогается,
                # потому что о самом адресе это ничего не говорит.
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
