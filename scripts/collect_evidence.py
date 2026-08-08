#!/usr/bin/env python3
"""Прогон сборщиков по технологиям реестра (STAGE-7 Ф8).

Для каждой технологии берёт её links, вызывает сборщики (arXiv/GitHub/OpenAlex),
прогоняет S5, и записывает прошедшие проверку свидетельства в evidence
(append-only). Без LLM-конфигурации ступени S3/S4 пропускаются — это нормально:
детерминированная часть даёт реальные уровни L0–L3 для технологий с
arXiv/GitHub-источниками.

Использование::

    python3 scripts/collect_evidence.py                 # все технологии
    python3 scripts/collect_evidence.py --limit 10      # первые 10 (для пробы)
    python3 scripts/collect_evidence.py --only pathrag  # одна технология
    python3 scripts/collect_evidence.py --compute-level # вычислить уровни после сбора

Требует DATABASE_URL и доступ к сети (arXiv/GitHub/OpenAlex в allowlist).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=0,
        help="ограничить число технологий (0 = все)",
    )
    parser.add_argument("--only", help="обработать только указанный technology_id")
    parser.add_argument(
        "--compute-level", action="store_true",
        help="после сбора вычислить уровни зрелости (core/maturity.py) "
             "и записать в maturity_history",
    )
    args = parser.parse_args()

    from datetime import date

    from core.maturity import compute_level
    from services.collectors.orchestrator import collect_for_links, record_collected
    from services.collectors.transport import RequestsTransport
    from services.db import connection as db
    from services.db import repository as repo

    if not db.is_configured():
        sys.stderr.write("DATABASE_URL не задан.\n")
        return 2

    transport = RequestsTransport()
    github_token = os.environ.get("GITHUB_TOKEN") or None
    today = date.today()

    # Список технологий.
    if args.only:
        techs = [repo.get_technology(args.only)]
        techs = [t for t in techs if t]
    else:
        techs = repo.list_technologies()
    if args.limit:
        techs = techs[: args.limit]

    total_evidence = 0
    total_level_changes = 0
    for tech in techs:
        full = repo.get_technology(tech.id)
        if not full or not full.links:
            continue
        links_data = [
            {"url": ln.url, "kind": ln.kind.value, "label": ln.label}
            for ln in full.links
        ]
        raws, checks, errors = collect_for_links(
            tech.id, links_data, http=transport, github_token=github_token, today=today
        )
        n = record_collected(tech.id, checks)
        total_evidence += n
        skipped = sum(1 for _, c in checks if not c.passed)
        status = f"+{n} evidence" + (f", {skipped} skipped" if skipped else "")
        if errors:
            status += f", errors={len(errors)}"
        print(f"{tech.id:<28} {status}", flush=True)

        if args.compute_level and n > 0:
            # Перечитать evidence и вычислить уровень.
            from services.collectors.base import RawEvidence

            evidence_in = []
            for ev in repo.list_evidence(tech.id):
                evidence_in.append(RawEvidence(
                    technology_id=tech.id,
                    type=ev.type.value, source=ev.source, value=ev.value,
                    fetched_at=ev.fetched_at, verified=ev.verified,
                ))
            result = compute_level(evidence_in, as_of=today)
            repo.record_maturity(
                technology_id=tech.id,
                level=result.level,
                confidence=result.confidence,
                rule_version="1.0.0",
                evidence_basis=result.evidence_basis,
            )
            total_level_changes += 1
            print(
                f"  → {result.level} (conf={result.confidence:.2f}, "
                f"{result.evidence_basis})",
                flush=True,
            )

    print(f"\nOK    собрано свидетельств: {total_evidence}")
    if args.compute_level:
        print(f"      вычислено уровней: {total_level_changes}")
    db.close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(main())
