#!/usr/bin/env python3
"""Update the portal in a single pass.

The only entry point of the chain. A person uses it through `make collect` and
the schedule uses it directly, so what the unattended run does matches what a
local run does by construction, and the workflow stays a wrapper with no logic
in it.

The order of the steps, and why it is this one:

1. **Collection** — the sources are asked, the deterministic checks run, and
   evidence and measurements are appended. A source refusing does not interrupt
   the pass: the remaining records are processed and the refusal reaches the run
   log.
2. **Links** — whether the registry's addresses resolve. A link rots in silence,
   and a record with no live source goes on looking grounded. A temporary
   refusal does not change the mark: publishers refuse robots, and taking that
   for the death of a link would spoil the registry faster than time spoils
   addresses.
3. **Discovery** — the catalogue is asked for the past week under the method
   tag. It creates no registry records and appends candidates to a queue where a
   person decides. A work that has been found is a supposition about a
   technology, not a technology.
4. **Levels** — recomputed by the rule, with no language model. Only a change
   reaches the level journal.
5. **Artefacts** — what the portal reads is rebuilt. The build is stable: with
   unchanged data the files come out byte for byte the same, so no spurious
   changes arise.
6. **Validation** — schema, references, the provenance of numbers. It runs
   **always**, even when the data did not change: it is cheap and it catches
   corruption rather than only an update. A failure ends the pass with an error,
   and it does so **before** anything is committed.
7. **The run log** — one line, always. It distinguishes "nobody looked" from
   "nothing happened" and serves as the sign of activity the platform wants: a
   schedule is disabled after sixty days without commits.
8. **The digest** — an issue about what changed, when anything did. No language
   model takes part: an issue retells what has already been computed, and there
   is nothing in it to invent. An empty issue is not published — the question
   whether anyone looked is answered by the run log, and the digest answers the
   question of what was found.

Usage::

    python3 scripts/update.py                 # the whole pass
    python3 scripts/update.py --limit 5       # the first five records, as a trial
    python3 scripts/update.py --only pathrag  # one record
    python3 scripts/update.py --skip-collect  # recomputation and build only
    python3 scripts/update.py --dry-run       # write nothing
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

#: Насколько часто перепроверять уже подтверждённую ссылку. Месяц — размен
#: между расходом чужих ресурсов и сроком, за который поломку заметят.
LINK_RECHECK_DAYS = 30


def run(
    *,
    limit: int = 0,
    only: str | None = None,
    skip_collect: bool = False,
    dry_run: bool = False,
    http=None,
    #: Отдельный транспорт для ссылок: у него снят перечень доменов,
    #: потому что реестр ссылается и на площадки вне его.
    link_http=None,
    today: date | None = None,
) -> int:
    import build_artifacts
    import build_digest
    import check_links
    import collect
    import compute_levels
    import validate_data

    today = today or date.today()

    # ─── 1. Сбор ─────────────────────────────────────────────────────────────
    if skip_collect:
        gathered = collect.CollectSummary()
    else:
        gathered = collect.gather(
            limit=limit, only=only, dry_run=dry_run, http=http, today=today
        )
        print(
            f"собрано: свидетельств {gathered.evidence_added}, "
            f"точек ряда {gathered.metrics_added}; "
            f"отклонено проверками {gathered.rejected}; "
            f"источников без результата {len(gathered.errors)}"
        )
        for message in gathered.errors[:10]:
            print(f"  {message[:130]}")
        if len(gathered.errors) > 10:
            print(f"  ещё {len(gathered.errors) - 10}")

    # ─── 2. Ссылки ───────────────────────────────────────────────────────────
    #
    # Ссылки гниют молча: площадка переезжает, препринт снимают, репозиторий
    # переименовывают, а запись продолжает выглядеть обоснованной. Проверка
    # идёт после сбора, потому что сбор мог добавить источники, и до
    # пересчёта уровней, чтобы испорченная ссылка была видна в том же прогоне.
    #
    # Недавно подтверждённые адреса пропускаются: за неделю ссылка, открытая
    # вчера, обычно не исчезает, а лишние обращения — расход чужих ресурсов.
    if not skip_collect:
        links = check_links.run(
            http=link_http, today=today, dry_run=dry_run,
            stale_after=LINK_RECHECK_DAYS,
        )
        print(
            f"ссылки: проверено {links.checked}, разрешается {links.verified}, "
            f"не существует {links.gone}, закрыто правами {links.guarded}"
        )
        for problem in links.problems[:10]:
            print(f"  {problem[:130]}")
        if len(links.problems) > 10:
            print(f"  ещё {len(links.problems) - 10}")
    else:
        links = check_links.LinkSummary()

    # ─── 3. Обнаружение ──────────────────────────────────────────────────────
    #
    # Записей не заводит: дописывает кандидатов в очередь, где их ждёт решение
    # человека. Отказ каталога проход не прерывает, как и отказ любого другого
    # источника.
    if not skip_collect:
        import discover

        found = discover.run(http=http, today=today, dry_run=dry_run)
        print(
            f"обнаружение: найдено {found.found}, в очередь добавлено "
            f"{found.added}, уже в реестре {found.known}"
        )
        gathered.errors.extend(found.problems)
    else:
        found = None

    # ─── 4. Уровни ───────────────────────────────────────────────────────────
    levels_changed = compute_levels.run(dry_run=dry_run, today=today)

    # ─── 5. Артефакты ────────────────────────────────────────────────────────
    if not dry_run:
        counts = build_artifacts.build()
        print(
            f"артефакты: технологий {counts['technologies']}, "
            f"записей хроники {counts['changes']}"
        )

    # ─── 6. Проверка ─────────────────────────────────────────────────────────
    problems = validate_data.check_registry()
    if problems:
        sys.stderr.write(f"проверка данных не пройдена: нарушений {len(problems)}\n")
        for problem in problems[:20]:
            sys.stderr.write(f"  {problem}\n")
        # Возврат с ошибкой до фиксации: испорченные данные публиковать нельзя.
        return 1
    print("проверка данных пройдена")

    # ─── 7. Журнал прогонов ──────────────────────────────────────────────────
    #
    # Проход без опроса источников в журнал сбора не попадает: строка «проверено
    # такого-то числа» при пустом перечне источников утверждала бы проверку,
    # которой не было. Такой проход — пересборка после правки кода, а не сбор.
    if not dry_run and not skip_collect:
        store.append_run(store.CollectionRun(
            ran_at=today,
            sources=gathered.sources,
            evidence_added=gathered.evidence_added,
            metrics_added=gathered.metrics_added,
            levels_changed=levels_changed,
            source_errors=len(gathered.errors),
            links_checked=links.checked,
            links_broken=links.gone,
            data_changed=bool(
                gathered.evidence_added or gathered.metrics_added
                or levels_changed or links.changed
            ),
        ))
        print(f"прогон записан в журнал: {store.COLLECTION_LOG.name}")

        # ─── 8. Дайджест ─────────────────────────────────────────────────────
        #
        # После журнала прогонов, потому что выпуск сообщает и о проверке
        # ссылок, и после проверки данных, потому что публиковать сообщение по
        # испорченным данным нельзя. Языковая модель не участвует: выпуск
        # пересказывает уже вычисленное, и выдумать в нём нечего — ровно
        # поэтому он публикуется без просмотра человеком.
        #
        # Пустой выпуск не выходит: неделя без изменений — обычное дело, а
        # полсотни сообщений «ничего не произошло» превратили бы дайджест в
        # шум. На вопрос «смотрели ли» отвечает журнал прогонов.
        issue = build_digest.build(today=today)
        if issue.has_news():
            path = build_digest.digest_dir() / f"{issue.issued_at.isoformat()}.json"
            if path.exists():
                print("выпуск дайджеста за сегодня уже есть, повторный не пишется")
            else:
                build_digest.publish(issue)
                print(f"выпуск дайджеста: {path.name}")
                # Лента и страница выпусков читают собранное, поэтому артефакты
                # пересобираются: без этого выпуск лежал бы в данных, но не
                # доходил до читателя.
                build_artifacts.build()
        else:
            print("дайджест: изменений нет, выпуск не собран")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="ограничить число записей")
    parser.add_argument("--only", help="обработать только указанную запись")
    parser.add_argument(
        "--skip-collect", action="store_true",
        help="не опрашивать источники, только пересчитать и пересобрать",
    )
    parser.add_argument("--dry-run", action="store_true", help="ничего не записывать")
    args = parser.parse_args()
    return run(
        limit=args.limit,
        only=args.only,
        skip_collect=args.skip_collect,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
