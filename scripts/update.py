#!/usr/bin/env python3
"""Обновление портала одним проходом.

Единственная точка входа цепочки. Ею пользуется и человек (`make collect`), и
расписание — поэтому поведение автономного прогона совпадает с локальным по
построению, а рабочий процесс остаётся обёрткой без логики.

Порядок шагов и почему он такой:

1. **Сбор** — опрос источников, детерминированные проверки, дозапись
   свидетельств и показателей. Отказ источника не прерывает проход: остальные
   записи обрабатываются, а отказ попадает в журнал прогонов.
2. **Уровни** — пересчёт правилом без языковой модели. В журнал уровней
   попадает только изменение.
3. **Артефакты** — пересборка того, что читает портал. Сборка устойчива: при
   неизменных данных файлы совпадают побайтово, поэтому лишних изменений не
   возникает.
4. **Проверка** — схема, ссылочная целостность, происхождение чисел.
   Выполняется **всегда**, даже когда данные не менялись: она дешёвая и ловит
   порчу, а не только обновление. Не прошла — проход завершается с ошибкой и
   **до** фиксации.
5. **Журнал прогонов** — одна строка, всегда. Она отличает «никто не смотрел»
   от «ничего не происходило» и служит признаком активности репозитория:
   расписание площадки отключается после шестидесяти дней без коммитов.

Использование::

    python3 scripts/update.py                 # полный проход
    python3 scripts/update.py --limit 5       # первые пять записей, для пробы
    python3 scripts/update.py --only pathrag  # одна запись
    python3 scripts/update.py --skip-collect  # только пересчёт и сборка
    python3 scripts/update.py --dry-run       # ничего не записывать
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402


def run(
    *,
    limit: int = 0,
    only: str | None = None,
    skip_collect: bool = False,
    dry_run: bool = False,
) -> int:
    import build_artifacts
    import collect
    import compute_levels
    import validate_data

    today = date.today()

    # ─── 1. Сбор ─────────────────────────────────────────────────────────────
    if skip_collect:
        gathered = collect.CollectSummary()
    else:
        gathered = collect.gather(limit=limit, only=only, dry_run=dry_run)
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

    # ─── 2. Уровни ───────────────────────────────────────────────────────────
    levels_changed = compute_levels.run(dry_run=dry_run)

    # ─── 3. Артефакты ────────────────────────────────────────────────────────
    if not dry_run:
        counts = build_artifacts.build()
        print(
            f"артефакты: технологий {counts['technologies']}, "
            f"записей хроники {counts['changes']}"
        )

    # ─── 4. Проверка ─────────────────────────────────────────────────────────
    problems = validate_data.check_registry()
    if problems:
        sys.stderr.write(f"проверка данных не пройдена: нарушений {len(problems)}\n")
        for problem in problems[:20]:
            sys.stderr.write(f"  {problem}\n")
        # Возврат с ошибкой до фиксации: испорченные данные публиковать нельзя.
        return 1
    print("проверка данных пройдена")

    # ─── 5. Журнал прогонов ──────────────────────────────────────────────────
    if not dry_run:
        store.append_run(store.CollectionRun(
            ran_at=today,
            sources=gathered.sources,
            evidence_added=gathered.evidence_added,
            metrics_added=gathered.metrics_added,
            levels_changed=levels_changed,
            source_errors=len(gathered.errors),
            data_changed=bool(
                gathered.evidence_added or gathered.metrics_added or levels_changed
            ),
        ))
        print(f"прогон записан в журнал: {store.COLLECTION_LOG.name}")

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
