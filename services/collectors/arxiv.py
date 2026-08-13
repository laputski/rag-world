"""Сборщик arXiv (STAGE-7 Ф8, план 03 §5.2 S1).

Опрашивает arXiv API по идентификатору публикации или запросу, извлекает
метаданные (заголовок, год, авторы) и возвращает кандидатные свидетельства
типа publication. Запись в БД делает оркестратор.

arXiv API: http://export.arxiv.org/api/query?id_list=XXXX.XXXXX
Возвращает Atom XML; заголовок в <entry><title>.

Ключевая роль:actual_title проверяется ступенью S5 на совпадение с ожидаемым
заголовком — та проверка, что нашла 3 ошибочные ссылки в рецензии (99-review).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

from services.collectors.base import CollectResult, HttpGetter, RawEvidence, is_allowed_host

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _extract_arxiv_id(url: str) -> str | None:
    """Извлечь arXiv-id из URL или вернуть само значение, если это уже id."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/[0-9]{7})", url, re.I)
    if m:
        return m.group(1)
    # голый id
    if re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}|[a-z\-]+/[0-9]{7}", url):
        return url
    return None


def _parse_atom_entries(xml_bytes: bytes) -> list[dict[str, str]]:
    """Извлечь записи из Atom-ответа arXiv: [{id, title, published, summary}]."""
    entries: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return entries
    for entry in root.findall(f"{ATOM_NS}entry"):
        arxiv_id = ""
        id_text = entry.findtext(f"{ATOM_NS}id", default="") or ""
        m = re.search(r"arxiv\.org/abs/([^/\s]+)", id_text)
        if m:
            arxiv_id = m.group(1)
        title = (entry.findtext(f"{ATOM_NS}title", default="") or "").strip()
        title = re.sub(r"\s+", " ", title)
        published = entry.findtext(f"{ATOM_NS}published", default="") or ""
        # Аннотация обещана описанием функции с самого начала, но не
        # извлекалась: обнаружение по курируемым спискам оценивает пригодность
        # именно по ней, и без неё оценка вырождается в догадку по заголовку.
        summary = (entry.findtext(f"{ATOM_NS}summary", default="") or "").strip()
        summary = re.sub(r"\s+", " ", summary)
        entries.append({
            "id": arxiv_id, "title": title,
            "published": published[:10], "summary": summary,
        })
    return entries


def collect_arxiv(
    technology_id: str,
    arxiv_id_or_url: str,
    *,
    http: HttpGetter,
    expected_title: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Собрать публикацию из arXiv по id/URL.

    Возвращает CollectResult с одним RawEvidence (publication), содержащим
    actual_title для проверки S5. expected_title — ожидаемый заголовок (из
    реестра/сида); если задан, S5 сравнит его с actual_title.
    """
    today = today or date.today()
    result = CollectResult(source_name="arxiv", technology_id=technology_id)

    arxiv_id = _extract_arxiv_id(arxiv_id_or_url)
    if not arxiv_id:
        result.errors.append(f"не удалось извлечь arXiv-id из {arxiv_id_or_url!r}")
        return result

    url = f"{ARXIV_API}?id_list={arxiv_id}"
    if not is_allowed_host(url):
        result.skipped.append(f"домен вне allowlist: {url}")
        return result

    status, body = http.get(url, timeout=20)
    if status != 200:
        result.errors.append(f"arXiv API вернул {status} для {arxiv_id}")
        return result

    entries = _parse_atom_entries(body)
    if not entries:
        result.errors.append(f"arXiv: нет записи для {arxiv_id}")
        return result

    entry = entries[0]
    actual_title = entry["title"]
    # published → год публикации (для проверки S5: год не противоречит препринту).
    year = entry["published"][:4] if entry["published"] else ""

    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value=f"arXiv:{arxiv_id} ({year})",
        source=f"https://arxiv.org/abs/{arxiv_id}",
        fetched_at=today,
        obtained_by="auto",
        verified=False,  # S5 решит, verified ли
        expected_title=expected_title,
        actual_title=actual_title,
    ))
    return result
