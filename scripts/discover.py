#!/usr/bin/env python3
"""Обнаружение новых работ: очередь кандидатов, а не записи реестра.

Найденная работа — не технология, а предположение о ней. Решение «это новая
архитектура, а не приложение существующей» принимает человек: правило здесь
ошибается, а цена ошибки — запись реестра о том, чего нет. Поэтому обнаружение
**не заводит записей** и дописывает строки в `data/candidates.jsonl`.

Журнал только добавляется, как свидетельства. Вердикт проставляется отдельно и
означает решение: `accepted` — запись реестра заведена, `rejected` — причина
записана, кандидат больше не всплывёт.

Отсев до просмотра делается машинно и без языковой модели: отбрасывается то,
что уже есть в реестре по номеру препринта либо по имени, и то, что уже
получило вердикт. Отсев по существу («это приложение, а не архитектура») машине
не поручается.

Использование::

    python3 scripts/discover.py                 # за неделю
    python3 scripts/discover.py --since 30      # за тридцать дней
    python3 scripts/discover.py --dry-run       # показать, не записывая
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.candidate_fit import assess  # noqa: E402
from services.collectors.curated import CURATED_LISTS, discover_from_lists  # noqa: E402
from services.collectors.paperswithcode import RAG_METHOD, Paper, discover  # noqa: E402
from services.registry import store  # noqa: E402

CANDIDATES = store.DATA_DIR / "candidates.jsonl"
REJECTED = store.DATA_DIR / "rejected.jsonl"

#: За какой срок спрашивать работы по умолчанию. Совпадает с шагом расписания:
#: сутки нахлёста дешевле пропуска, а повтор отсеется по номеру препринта.
DEFAULT_WINDOW_DAYS = 8

#: Окно для курируемых списков: два года вместо недели.
#:
#: Список пополняется не по расписанию, а когда у ведущего дошли руки, и работа
#: может попасть в него через полгода после выхода. Недельное окно, годное для
#: каталога, отсекло бы ровно то, ради чего список и опрашивается. Отсев по
#: известному при этом идёт до обращения к arXiv, поэтому широкое окно стоит
#: одного разбора разметки, а не сотни запросов.
CURATED_WINDOW_DAYS = 730

_ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})")


@dataclass
class DiscoverySummary:
    """Итог обнаружения: что найдено, что отсеяно и почему."""

    found: int = 0
    added: int = 0
    known: int = 0
    decided: int = 0
    rescored: int = 0
    problems: list[str] = field(default_factory=list)


def load_candidates() -> list[dict]:
    if not CANDIDATES.exists():
        return []
    return [
        json.loads(line)
        for line in CANDIDATES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _registry_arxiv_ids() -> set[str]:
    """Номера препринтов, на которые уже ссылается реестр."""
    found: set[str] = set()
    for tech in store.load_technologies():
        for link in tech.links:
            match = _ARXIV_ID.search(link.url)
            if match:
                found.add(match.group(1))
    return found


def _registry_names() -> set[str]:
    names: set[str] = set()
    for tech in store.load_technologies():
        names.add(tech.name.strip().lower())
        names |= {alias.strip().lower() for alias in tech.aliases}
    return names


def _rejected_names() -> set[str]:
    if not REJECTED.exists():
        return set()
    out: set[str] = set()
    for line in REJECTED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        row = json.loads(line)
        name = row.get("name")
        if name:
            out.add(name.strip().lower())
    return out


def is_known(paper: Paper, *, arxiv_ids: set[str], names: set[str]) -> bool:
    """Работа уже описана реестром либо отклонена прежде.

    Сверка идёт по номеру препринта и по имени. Имя сравнивается целиком: имя
    работы обычно длиннее имени технологии, поэтому совпадение по вхождению
    дало бы ложные срабатывания на общих словах.
    """
    if paper.arxiv_id in arxiv_ids:
        return True
    title = paper.title.strip().lower()
    if title in names:
        return True
    # Заголовок вида «HippoRAG: Neurobiologically Inspired…»: имя стоит до
    # двоеточия, и по нему запись реестра узнаётся.
    head = title.split(":", 1)[0].strip()
    return bool(head) and head in names


def run(
    *,
    since_days: int = DEFAULT_WINDOW_DAYS,
    today: date | None = None,
    http=None,
    dry_run: bool = False,
) -> DiscoverySummary:
    today = today or date.today()
    if http is None:
        from services.collectors.transport import RequestsTransport

        http = RequestsTransport()

    summary = DiscoverySummary()
    papers, problems = discover(
        http=http, published_after=today - timedelta(days=since_days),
        method=RAG_METHOD,
    )
    summary.problems.extend(problems)

    arxiv_ids = _registry_arxiv_ids()
    names = _registry_names() | _rejected_names()
    seen = {row.get("arxiv_id") for row in load_candidates()}
    decided = {
        row.get("arxiv_id") for row in load_candidates() if row.get("verdict")
    }

    # Второй путь обнаружения: курируемые тематические списки.
    #
    # Каталог находит работу по метке, проставленной тем, кто её выложил.
    # Список находит работу по решению человека, который в предмете работает.
    # Пути дополняют друг друга, и работа, найденная обоими, — не повтор, а
    # согласие двух независимых отборов.
    #
    # Известное отсеивается до обращения к arXiv: в списке сотня с лишним
    # работ, из которых новых единицы, и спрашивать аннотации по всем значило
    # бы бить по чужой службе впустую.
    listed, listed_problems = discover_from_lists(
        http=http,
        published_after=today - timedelta(days=CURATED_WINDOW_DAYS),
        known=arxiv_ids | seen | decided,
    )
    summary.problems.extend(listed_problems)
    curated_source = {paper.arxiv_id for paper in listed}
    papers = papers + listed
    summary.found = len(papers)

    fresh: list[dict] = []
    for paper in papers:
        if is_known(paper, arxiv_ids=arxiv_ids, names=names):
            summary.known += 1
            continue
        if paper.arxiv_id in decided:
            summary.decided += 1
            continue
        if paper.arxiv_id in seen:
            continue  # уже в очереди и ждёт решения
        curated = sorted(
            source.name for source in CURATED_LISTS
            if paper.arxiv_id in curated_source
        )
        fit = assess(title=paper.title, abstract=paper.abstract,
                     tasks=[{"slug": slug} for slug in paper.tasks],
                     curated_by=curated)
        fresh.append({
            "found_at": today.isoformat(),
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "tasks": paper.tasks,
            "fit": fit.as_dict(),
            "published": paper.published.isoformat() if paper.published else None,
            "source": paper.url,
            "citations": paper.citations,
            "repositories": paper.repositories,
            # Откуда работа пришла. Нужно при разборе очереди: находка по
            # списку и находка по каталогу подтверждены разным, и знать это
            # человеку полезнее, чем видеть одно число пригодности.
            "curated_by": curated,
            "verdict": None,
        })

    summary.added = len(fresh)
    if fresh and not dry_run:
        CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
        with CANDIDATES.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    summary.rescored = rescore(dry_run=dry_run)
    return summary


def rescore(*, dry_run: bool = False) -> int:
    """Пересчитать оценку у кандидатов, ждущих решения.

    Правило оценки меняется чаще, чем очередь: список меток уточняется по мере
    того, как видно, что каталог действительно проставляет. Кандидат, лежащий
    в очереди третью неделю, должен оцениваться нынешним правилом, а не тем,
    что действовало в день находки, иначе порядок просмотра врёт.

    Сети не требует: метки задач, аннотация и происхождение находки хранятся
    вместе с кандидатом. Происхождение приходится передавать обратно в оценку
    явно: пересчёт идёт по строке очереди, и признак, выведенный при находке,
    но не сохранённый, был бы при пересчёте потерян. Один раз так и вышло —
    оценки работ, найденных по спискам, обнулялись первым же пересчётом.
    """
    rows = load_candidates()
    if not rows:
        return 0
    changed = 0
    for row in rows:
        if row.get("verdict"):
            continue
        fit = assess(
            title=row.get("title", ""),
            abstract=row.get("abstract", ""),
            tasks=[{"slug": slug} for slug in row.get("tasks", [])],
            curated_by=row.get("curated_by") or None,
        ).as_dict()
        if row.get("fit") != fit:
            row["fit"] = fit
            changed += 1
    if changed and not dry_run:
        CANDIDATES.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
            + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=int, default=DEFAULT_WINDOW_DAYS,
                        help="за сколько дней спрашивать работы")
    parser.add_argument("--dry-run", action="store_true", help="ничего не записывать")
    args = parser.parse_args()

    summary = run(since_days=args.since, dry_run=args.dry_run)
    print(
        f"обнаружение: найдено {summary.found}, в очередь добавлено "
        f"{summary.added}, уже в реестре {summary.known}, решено прежде "
        f"{summary.decided}, оценка пересчитана у {summary.rescored}"
    )
    for problem in summary.problems[:10]:
        print(f"  {problem[:140]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
