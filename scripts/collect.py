#!/usr/bin/env python3
"""Сбор свидетельств из открытых источников.

Первый шаг цепочки обновления. Обходит источники каждой записи реестра,
опрашивает архив препринтов, открытый индекс, площадку репозиториев и
каталог работ и кода, прогоняет детерминированные проверки и
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
from dataclasses import dataclass, field
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
        # Каталог работ и кода опрашивается по тому же номеру препринта. Он
        # даёт площадку публикации вторым источником: пока она приходила только
        # из открытого индекса, ошибка индекса ничем не перекрывалась.
        return ["arxiv", "openalex", "paperswithcode"]
    if "github.com" in url:
        return ["github"]
    if "openalex.org" in url:
        return ["openalex"]
    return []


def _collect_one(
    tech: store.Technology, *, http, github_token: str | None, today: date
) -> tuple[list[RawEvidence], list[str]]:
    from services.collectors.arxiv import _extract_arxiv_id, collect_arxiv
    from services.collectors.github import collect_github
    from services.collectors.openalex import collect_openalex
    from services.collectors.paperswithcode import collect_venue

    raw: list[RawEvidence] = []
    errors: list[str] = []
    for link in tech.links:
        for kind in _collectors_for(link.url):
            if kind == "arxiv":
                # Подпись ссылки заголовком работы не является: там пометки
                # вроде «CausalRAG (arXiv:2503.19878, ACL 2025)» и «исправлено:
                # было 2406.18542». Сравнение их с настоящим заголовком
                # отклоняло тринадцать законных публикаций каждый прогон.
                #
                # Проверять здесь нечего и по существу: у ссылки указан номер
                # архива, и запрос по номеру возвращает ровно ту работу.
                # Сверка заголовков нужна там, где работа ищется поиском, —
                # в открытом индексе, и там она есть.
                result = collect_arxiv(
                    tech.id, link.url, http=http, today=today,
                )
            elif kind == "github":
                result = collect_github(
                    tech.id, link.url, http=http, token=github_token, today=today,
                )
            elif kind == "paperswithcode":
                # Каталог спрашивается по номеру препринта, а не по адресу:
                # он отвечает лентой свежайших работ на всё, чего не понял, и
                # такой ответ выглядит осмысленным.
                number = _extract_arxiv_id(link.url)
                if not number:
                    continue
                result = collect_venue(tech.id, number, http=http, today=today)
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


@dataclass
class CollectSummary:
    """Итог сбора: что добавлено и что не получилось.

    Возвращается вызывающему, а не печатается: журнал прогонов записывает эти
    числа, и они же попадают в сводку прохода.
    """

    sources: list[str] = field(default_factory=list)
    evidence_added: int = 0
    metrics_added: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


def gather(
    *,
    limit: int = 0,
    only: str | None = None,
    dry_run: bool = False,
    http=None,
    today: date | None = None,
) -> CollectSummary:
    """Опросить источники и дописать прошедшие проверку свидетельства.

    `http` и `today` внедряются: без этого прогон нельзя проверить без сети, а
    непроверенный автономный прогон опаснее ручного запуска.
    """
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport()
    today = today or date.today()
    github_token = os.environ.get("GITHUB_TOKEN") or None

    technologies = store.load_technologies()
    if only:
        technologies = [t for t in technologies if t.id == only]
        if not technologies:
            raise SystemExit(f"Технология {only!r} не найдена в реестре.")
    if limit:
        technologies = technologies[:limit]

    summary = CollectSummary(sources=["arxiv", "openalex", "github", "paperswithcode"])
    accepted: list[store.Evidence] = []
    raw_all: list[RawEvidence] = []

    for tech in technologies:
        raw, tech_errors = _collect_one(
            tech, http=http, github_token=github_token, today=today
        )
        summary.errors.extend(tech_errors)
        raw_all.extend(raw)

    # Присутствие во фреймворках опрашивается один раз на весь реестр:
    # читаются оглавления каталогов, а не запись за записью.
    from services.collectors.frameworks import collect_frameworks

    framework_evidence, framework_errors = collect_frameworks(
        technologies, http=http, token=github_token, today=today
    )
    raw_all.extend(framework_evidence)
    summary.errors.extend(framework_errors)
    if framework_evidence or not framework_errors:
        summary.sources.append("frameworks")

    # Загрузки пакета — только там, где имя пакета записано человеком.
    from services.collectors.pypi import collect_pypi

    polled_pypi = False
    for tech in technologies:
        if not tech.package:
            continue
        polled_pypi = True
        result = collect_pypi(tech.id, tech.package, http=http, today=today)
        raw_all.extend(result.evidence)
        summary.errors.extend(result.errors)
    if polled_pypi:
        summary.sources.append("pypi")

    for item, check in check_many(raw_all):
        if not check.passed:
            summary.rejected += 1
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
    if manual:
        summary.sources.append("manual")
    points = _metrics_from(accepted)

    if dry_run:
        summary.evidence_added = len(accepted) + len(manual)
        summary.metrics_added = len(points)
    else:
        summary.evidence_added = store.append_evidence(accepted + manual)
        summary.metrics_added = store.append_metrics(points)
    return summary


def run(*, limit: int = 0, only: str | None = None, dry_run: bool = False) -> int:
    """Отдельный запуск только сбора; полный проход — в scripts/update.py."""
    summary = gather(limit=limit, only=only, dry_run=dry_run)
    prefix = "будет добавлено" if dry_run else "добавлено"
    print(
        f"{prefix}: свидетельств {summary.evidence_added}, "
        f"точек ряда {summary.metrics_added}; "
        f"отклонено проверками {summary.rejected}"
    )
    if summary.errors:
        print(f"источники без результата: {len(summary.errors)}")
        for message in summary.errors[:10]:
            print(f"  {message[:130]}")
        if len(summary.errors) > 10:
            print(f"  ещё {len(summary.errors) - 10}")
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
