#!/usr/bin/env python3
"""Разовый перенос реестра из локальной базы в файлы `data/`.

Скрипт выполняется один раз при переходе на файловое хранилище (ADR-004). После
переноса база остаётся вспомогательным инструментом и в цепочке обновления не
участвует.

Что переносится: записи технологий с их источниками, свидетельства и журнал
уровней. Что **не** переносится:

* признак принадлежности к «перспективным» — деление отменено (ADR-007);
* поле уровня парадигмы, существовавшее только ради этого деления;
* показатели без происхождения.

Использование::

    python3 scripts/migrate_to_files.py --dry-run   # показать, что будет перенесено
    python3 scripts/migrate_to_files.py             # выполнить перенос

Требует DATABASE_URL и установленного драйвера: pip install -e ".[migration]".
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402


def _link_kind(raw: str) -> str:
    allowed = {"paper", "preprint", "github", "product", "venue", "other"}
    return raw if raw in allowed else "other"


def migrate(dry_run: bool = False) -> int:
    from services.db import connection as db
    from services.db import repository as repo

    if not db.is_configured():
        sys.stderr.write(
            "DATABASE_URL не задан. Перенос выполняется один раз с рабочей базы;\n"
            "если база уже недоступна, реестр в data/ считается актуальным.\n"
        )
        return 2

    technologies = repo.list_technologies()
    if not technologies:
        sys.stderr.write("В базе нет записей — переносить нечего.\n")
        return 1

    n_links = n_evidence = n_levels = 0
    for summary in technologies:
        full = repo.get_technology(summary.id)
        links = [
            store.Link(
                url=link.url,
                kind=_link_kind(link.kind.value),
                label=link.label,
                status=link.status.value,
                verified_at=link.verified_at,
            )
            for link in (full.links if full else [])
        ]
        n_links += len(links)

        tech = store.Technology(
            id=summary.id,
            name=summary.name,
            aliases=list(summary.aliases),
            kind=summary.kind.value,
            family=summary.family,
            groups=[g.value for g in summary.groups],
            configuration=dict(summary.configuration),
            residual=list(summary.residual),
            core_idea=summary.core_idea,
            prose_id=summary.prose_id,
            first_published=None,
            links=links,
        )
        if not dry_run:
            store.save_technology(tech)

        evidence = [
            store.Evidence(
                technology_id=item.technology_id,
                type=item.type.value,
                value=item.value,
                source=item.source,
                fetched_at=item.fetched_at,
                obtained_by="auto" if item.obtained_by == "auto" else "manual",
                verified=item.verified,
            )
            for item in repo.list_evidence(summary.id)
        ]
        n_evidence += len(evidence)
        if not dry_run:
            store.append_evidence(evidence)

        latest = repo.latest_maturity(summary.id)
        if latest is not None:
            level, confidence, basis = latest
            entry = store.LevelEntry(
                technology_id=summary.id,
                level=level,
                confidence=confidence,
                evidence_basis="manual" if basis == "manual" else "computed",
                rule_version="1.0.0",
                computed_at=date.today(),
                evidence_snapshot=[
                    {"type": e.type, "source": e.source} for e in evidence
                ],
            )
            n_levels += 1
            if not dry_run:
                store.append_level(entry)

    prefix = "будет перенесено" if dry_run else "перенесено"
    print(f"{prefix}: технологий {len(technologies)}, источников {n_links}, "
          f"свидетельств {n_evidence}, уровней {n_levels}")
    if dry_run:
        print("Записи не изменены (--dry-run).")
    else:
        print(f"Каталог данных: {store.DATA_DIR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="показать объём переноса, ничего не записывая",
    )
    args = parser.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
