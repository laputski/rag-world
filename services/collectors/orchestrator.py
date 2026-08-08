"""Оркестратор сбора свидетельств (STAGE-7 Ф8).

Связывает сборщики (arXiv, OpenAlex, GitHub) с реестром и БД:
  1. Для каждой технологии берёт её links (URL-источники).
  2. По типу URL выбирает сборщик, опрашивает источник (через инъектируемый HTTP).
  3. Прогоняет детерминированную проверку S5.
  4. Прошедшие проверку свидетельства записывает в evidence (append-only).

Запись в БД опциональна (dry_run для тестов/CI без БД). HTTP-клиент
инъектируется — тесты подменяют без сети.
"""

from __future__ import annotations

from datetime import date

from services.collectors.base import CollectResult, HttpGetter, RawEvidence
from services.collectors.s5 import CheckResult, check_many


def _select_collector(url: str) -> str:
    """Выбрать имя сборщика по URL."""
    if "arxiv.org" in url:
        return "arxiv"
    if "github.com" in url:
        return "github"
    if "openalex.org" in url:
        return "openalex"
    return ""


def collect_for_links(
    technology_id: str,
    links: list[dict],  # [{url, kind, label, ...}] из реестра
    *,
    http: HttpGetter,
    github_token: str | None = None,
    today: date | None = None,
) -> tuple[list[RawEvidence], list[CheckResult], list[str]]:
    """Собрать свидетельства по links технологии; вернуть (raw, checks, errors).

    НЕ записывает в БД — это делает record_collected(). Разделение позволяет
    тестировать сбор без БД.
    """
    today = today or date.today()
    all_raw: list[RawEvidence] = []
    errors: list[str] = []

    for link in links:
        url = link.get("url", "")
        kind = _select_collector(url)
        if not kind:
            continue  # URL вне источников (atlan.com, anthropic.com/blog и т.п.)

        # expected_title: из label реестра, если есть (грубая подсказка для S5).
        expected = link.get("label")

        result = CollectResult(source_name=kind, technology_id=technology_id)
        if kind == "arxiv":
            from services.collectors.arxiv import collect_arxiv
            result = collect_arxiv(technology_id, url, http=http,
                                   expected_title=expected, today=today)
        elif kind == "github":
            from services.collectors.github import collect_github
            result = collect_github(technology_id, url, http=http,
                                    token=github_token, today=today)
        elif kind == "openalex":
            from services.collectors.openalex import collect_openalex
            result = collect_openalex(technology_id, url, http=http,
                                      expected_title=expected, today=today)

        all_raw.extend(result.evidence)
        errors.extend(result.errors)

    checks = check_many(all_raw)
    return all_raw, checks, errors


def record_collected(
    technology_id: str,
    checks: list[tuple[RawEvidence, CheckResult]],
) -> int:
    """Записать прошедшие S5 свидетельства в БД (evidence, append-only).

    Возвращает число записанных. Не записывает непрошедшие (они логируются
    в журнале конвейера — Ф9). Требует DATABASE_URL.
    """
    from services.db import repository as repo

    n = 0
    for ev, res in checks:
        if not res.passed:
            continue
        repo.add_evidence(
            technology_id=technology_id,
            type=ev.type,
            source=ev.source,
            value=ev.value,
            fetched_at=ev.fetched_at.isoformat(),
            obtained_by=ev.obtained_by,
            verified=True,  # прошло S5
        )
        n += 1
    return n
