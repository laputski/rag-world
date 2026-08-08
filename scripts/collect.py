#!/usr/bin/env python3
"""Сбор свидетельств из открытых источников.

Первый шаг цепочки обновления. Обходит источники каждой записи реестра,
опрашивает arXiv, OpenAlex и GitHub, прогоняет детерминированные проверки и
дописывает прошедшие свидетельства в журнал. Языковая модель не участвует.

Проверки принципиально детерминированные: разрешимость идентификатора,
совпадение заголовка, допустимость диапазона. Согласие двух языковых моделей
подтверждением не считается — они обучены на пересекающихся данных и ошибаются
согласованно.

Отдельно загружается файл свидетельств, вводимых человеком
(`data/manual_evidence.jsonl`). Он нужен там, где машиночитаемого источника не
существует: промышленное применение, независимое воспроизведение, публикация на
площадке, которую открытые индексы не знают. Каждая такая запись обязана нести
ссылку и помечается как введённая человеком.

Использование::

    python3 scripts/collect.py                 # все записи
    python3 scripts/collect.py --limit 5       # первые пять, для пробы
    python3 scripts/collect.py --only pathrag  # одна запись
    python3 scripts/collect.py --dry-run       # ничего не записывать
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.collectors.base import RawEvidence  # noqa: E402
from services.collectors.s5 import check_many  # noqa: E402
from services.registry import store  # noqa: E402

MANUAL_FILE = store.DATA_DIR / "manual_evidence.jsonl"

_VELOCITY_RE = re.compile(r"citation_velocity=([0-9.]+)")
_ARXIV_HOST = "arxiv.org"


def _collectors_for(url: str) -> list[str]:
    """Какие сборщики применимы к источнику.

    Адрес arXiv опрашивается дважды: сам архив даёт факт препринта, а открытый
    индекс — площадку публикации и цитирования. Без второго запроса работа
    навсегда осталась бы препринтом, даже если вышла на конференции.
    """
    if _ARXIV_HOST in url:
        return ["arxiv", "openalex"]
    if "github.com" in url:
        return ["github"]
    if "openalex.org" in url:
        return ["openalex"]
    return []


def _collect_one(
    tech: store.Technology, *, http, github_token: str | None, today: date
) -> tuple[list[RawEvidence], list[str]]:
    from services.collectors.arxiv import collect_arxiv
    from services.collectors.github import collect_github
    from services.collectors.openalex import collect_openalex

    raw: list[RawEvidence] = []
    errors: list[str] = []
    for link in tech.links:
        for kind in _collectors_for(link.url):
            if kind == "arxiv":
                result = collect_arxiv(
                    tech.id, link.url, http=http,
                    expected_title=link.label, today=today,
                )
            elif kind == "github":
                result = collect_github(
                    tech.id, link.url, http=http, token=github_token, today=today,
                )
            else:
                result = collect_openalex(
                    tech.id, link.url, http=http,
                    expected_title=tech.name, today=today,
                )
            raw.extend(result.evidence)
            errors.extend(f"{tech.id}: {e}" for e in result.errors)
    return raw, errors


def _metrics_from(evidence: list[store.Evidence]) -> list[store.MetricPoint]:
    """Временной ряд внимания из значений собранных свидетельств.

    Абсолютное число цитирований как показатель не сохраняется: оно несравнимо
    между областями и устаревает сразу. Сохраняется скорость цитирования.
    """
    points: list[store.MetricPoint] = []
    for item in evidence:
        match = _VELOCITY_RE.search(item.value or "")
        if match:
            points.append(store.MetricPoint(
                technology_id=item.technology_id,
                metric="citation_velocity",
                value=float(match.group(1)),
                measured_at=item.fetched_at,
                source=item.source,
            ))
    return points


def load_manual_evidence() -> list[store.Evidence]:
    """Свидетельства, введённые человеком; каждое обязано нести ссылку."""
    if not MANUAL_FILE.exists():
        return []
    import json

    out: list[store.Evidence] = []
    for line in MANUAL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        row.setdefault("obtained_by", "manual")
        row.setdefault("verified", True)
        out.append(store.Evidence.model_validate(row))
    return out


def run(*, limit: int = 0, only: str | None = None, dry_run: bool = False) -> int:
    from services.collectors.transport import RequestsTransport

    today = date.today()
    http = RequestsTransport()
    github_token = os.environ.get("GITHUB_TOKEN") or None

    technologies = store.load_technologies()
    if only:
        technologies = [t for t in technologies if t.id == only]
        if not technologies:
            sys.stderr.write(f"Технология {only!r} не найдена в реестре.\n")
            return 1
    if limit:
        technologies = technologies[:limit]

    accepted: list[store.Evidence] = []
    rejected = 0
    errors: list[str] = []

    for tech in technologies:
        raw, tech_errors = _collect_one(
            tech, http=http, github_token=github_token, today=today
        )
        errors.extend(tech_errors)
        for item, check in check_many(raw):
            if not check.passed:
                rejected += 1
                continue
            accepted.append(store.Evidence(
                technology_id=item.technology_id,
                type=item.type,  # type: ignore[arg-type]
                value=item.value,
                source=item.source,
                fetched_at=item.fetched_at,
                obtained_by="auto",
                verified=True,
            ))

    manual = load_manual_evidence()
    points = _metrics_from(accepted)

    if dry_run:
        print(
            f"будет добавлено: свидетельств {len(accepted)} автоматических и "
            f"{len(manual)} введённых человеком, точек ряда {len(points)}; "
            f"отклонено проверками {rejected}"
        )
    else:
        added = store.append_evidence(accepted + manual)
        added_points = store.append_metrics(points)
        print(
            f"добавлено: свидетельств {added} (новых из {len(accepted) + len(manual)}), "
            f"точек ряда {added_points}; отклонено проверками {rejected}"
        )

    if errors:
        print(f"источники без результата: {len(errors)}")
        for message in errors[:10]:
            print(f"  {message[:130]}")
        if len(errors) > 10:
            print(f"  ещё {len(errors) - 10}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="ограничить число записей")
    parser.add_argument("--only", help="обработать только указанную запись")
    parser.add_argument("--dry-run", action="store_true", help="ничего не записывать")
    args = parser.parse_args()
    return run(limit=args.limit, only=args.only, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
