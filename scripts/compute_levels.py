#!/usr/bin/env python3
"""Recompute maturity levels from the collected evidence.

The second step of the update chain. The rule is deterministic and uses no
language model: the same evidence always yields the same level, so any value
reproduces on a rerun.

Only a **change** of level reaches the journal. A recomputation that changed
nothing leaves it untouched; otherwise the journal would become a log of runs,
whereas what is wanted from it is a chronicle.

Usage::

    python3 scripts/compute_levels.py
    python3 scripts/compute_levels.py --dry-run   # show what would change
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.maturity import RULE_VERSION, EvidenceIn, compute_level  # noqa: E402
from services.registry import store  # noqa: E402


def run(
    dry_run: bool = False, quiet: bool = False, today: date | None = None
) -> int:
    # Дата внедряется: правило зависит от возраста свидетельств, поэтому при
    # чтении с часов один и тот же набор данных давал бы разные уровни в разные
    # дни, и воспроизводимость нельзя было бы проверить.
    today = today or date.today()
    technologies = store.load_technologies()

    by_tech: dict[str, list[store.Evidence]] = defaultdict(list)
    for item in store.load_evidence():
        by_tech[item.technology_id].append(item)

    changes: list[tuple[str, str | None, str]] = []
    distribution: Counter[str] = Counter()

    for tech in technologies:
        evidence = by_tech.get(tech.id, [])
        if not evidence:
            # Без свидетельств уровень не вычисляется. Подставлять L0 нельзя:
            # «не изучено» и «гипотеза» — разные утверждения.
            distribution["нет данных"] += 1
            continue

        result = compute_level(
            [
                EvidenceIn(
                    type=e.type,
                    source=e.source,
                    value=e.value,
                    fetched_at=e.fetched_at,
                    verified=e.verified,
                )
                for e in evidence
            ],
            as_of=today,
        )
        distribution[result.level] += 1

        previous = store.latest_level(tech.id)
        if previous is not None and previous.level == result.level:
            continue

        changes.append((tech.id, previous.level if previous else None, result.level))
        if not dry_run:
            store.append_level(store.LevelEntry(
                technology_id=tech.id,
                level=result.level,
                confidence=round(result.confidence, 3),
                evidence_basis=result.evidence_basis,  # type: ignore[arg-type]
                rule_version=RULE_VERSION,
                computed_at=today,
                evidence_snapshot=[
                    {"type": e.type, "source": e.source} for e in evidence
                ],
            ))

    if not quiet:
        prefix = "изменится" if dry_run else "изменено"
        print(f"{prefix} уровней: {len(changes)} из {len(technologies)} записей")
        for tech_id, before, after in changes[:20]:
            print(f"  {tech_id:24} {before or 'нет данных':>10} → {after}")
        if len(changes) > 20:
            print(f"  ещё {len(changes) - 20}")

        print("распределение: " + ", ".join(
            f"{level} — {count}" for level, count in sorted(distribution.items())
        ))
    # Возвращается число изменённых уровней: его записывает журнал прогонов.
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="ничего не записывать")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
