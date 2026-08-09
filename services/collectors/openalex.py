"""Сборщик OpenAlex: площадка публикации и цитирования.

OpenAlex — открытый индекс научных работ. Из него берутся две вещи:

* **класс площадки** — рецензируемая конференция или журнал против препринта.
  Это единственный машиночитаемый путь к уровню L2 по научной линии: без него
  любая работа остаётся препринтом, каким бы известным ни был её результат;
* **цитирования и дата публикации** — из них выводится скорость цитирования,
  то есть внимание. Абсолютное число цитирований в представления не попадает:
  оно устаревает в момент измерения и несравнимо между областями.

Поиск идёт в два шага. Сначала работа находится по идентификатору arXiv через
его канонический DOI. Затем по названию ищутся остальные её версии: препринт и
конференционная публикация — это разные записи индекса, и рецензирование видно
только у второй.

Языковая модель не используется: все решения принимаются по полям ответа.
"""

from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import quote

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

OPENALEX_API = "https://api.openalex.org"

#: Открытый индекс держит два потока обращений: общий и вежливый. Во втором
#: лимиты заметно выше, и попасть туда можно, назвав почту для связи — так
#: устроено у них намеренно. Без этого прогон упирается в отказ по частоте, и
#: половина записей остаётся без сведений о площадке публикации.
#:
#: Почта берётся из окружения, а не вписывается в код: репозиторий читают
#: посторонние, и личный адрес в нём — не то, что стоит публиковать.
OPENALEX_MAILTO_ENV = "OPENALEX_MAILTO"


def _polite(url: str) -> str:
    """Добавить к адресу почту для связи, если она задана в окружении."""
    import os

    mailto = os.environ.get(OPENALEX_MAILTO_ENV, "").strip()
    if not mailto:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}mailto={quote(mailto)}"

_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5})", re.I)
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")

#: Типы площадок OpenAlex, означающие рецензирование. Тип `repository` — это
#: архив препринтов (arXiv и подобные), он рецензирование не подтверждает.
PEER_REVIEWED_SOURCE_TYPES = frozenset({"journal", "conference", "book series"})

#: Типы работы, означающие рецензирование. Препринт имеет собственный тип,
#: поэтому различие надёжно даже тогда, когда название площадки не заполнено.
PEER_REVIEWED_WORK_TYPES = frozenset({
    "article", "conference-paper", "proceedings-article", "book-chapter", "review",
})

#: Площадки, которые по типу выглядят журналом, но рецензирования не означают.
#: Сравнение по вхождению: индекс называет архив «arXiv (Cornell University)».
NOT_PEER_REVIEWED_MARKERS = ("arxiv", "biorxiv", "medrxiv", "ssrn", "preprint")

#: Префикс DOI однозначно указывает издателя. Это спасает, когда индекс не
#: заполнил название площадки: у конференционных публикаций такое встречается
#: часто, а знать площадку необходимо для вывода об уровне.
DOI_PREFIX_VENUES: dict[str, str] = {
    "10.18653": "ACL Anthology",
    "10.1145": "ACM",
    "10.1109": "IEEE",
    "10.1038": "Nature Portfolio",
    "10.1162": "MIT Press",
    "10.1609": "AAAI",
    "10.24963": "IJCAI",
    "10.14778": "VLDB Endowment",
    "10.1007": "Springer",
    "10.1016": "Elsevier",
    "10.1093": "Oxford University Press",
}

#: Префикс DOI архива препринтов: рецензирования не означает.
PREPRINT_DOI_PREFIX = "10.48550"


def _is_preprint_venue(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in NOT_PEER_REVIEWED_MARKERS)


def _doi_prefix(work: dict) -> str:
    doi = (work.get("doi") or "").lower()
    match = re.search(r"(10\.\d{4,9})/", doi)
    return match.group(1) if match else ""


def _get_json(http: HttpGetter, url: str, result: CollectResult) -> dict | None:
    if not is_allowed_host(url):
        result.skipped.append(f"домен вне allowlist: {url}")
        return None
    status, body = http.get(
        url, headers={"User-Agent": "rag-world/0.2 (registry collector)"}, timeout=20
    )
    if status != 200:
        result.errors.append(f"OpenAlex вернул {status}")
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        result.errors.append("OpenAlex: некорректный JSON")
        return None


def _venue_of(work: dict) -> tuple[str, bool]:
    """Название площадки и признак рецензирования.

    Решение принимается по трём признакам в порядке надёжности: тип площадки в
    индексе, тип самой работы и издательский префикс DOI. Последние два нужны
    потому, что у части конференционных публикаций название площадки в индексе
    просто отсутствует, и по одному лишь первому признаку они выглядели бы
    препринтами.
    """
    prefix = _doi_prefix(work)
    work_type = (work.get("type") or "").strip().lower()
    is_preprint_doi = prefix == PREPRINT_DOI_PREFIX

    best_name = ""
    for location in [work.get("primary_location") or {}, *(work.get("locations") or [])]:
        source = (location or {}).get("source") or {}
        name = (source.get("display_name") or "").strip()
        source_type = (source.get("type") or "").strip().lower()
        if not name:
            continue
        if _is_preprint_venue(name):
            best_name = best_name or name
            continue
        if source_type in PEER_REVIEWED_SOURCE_TYPES:
            return name, True
        best_name = best_name or name

    if not is_preprint_doi and work_type in PEER_REVIEWED_WORK_TYPES:
        venue = DOI_PREFIX_VENUES.get(prefix) or best_name or f"DOI {prefix}"
        return venue, True

    return best_name, False


def _citation_velocity(work: dict, today: date) -> float | None:
    """Цитирования, делённые на число месяцев с публикации."""
    cited = work.get("cited_by_count")
    published = work.get("publication_date") or ""
    if cited is None or not published:
        return None
    try:
        year, month = int(published[:4]), int(published[5:7])
    except (ValueError, IndexError):
        return None
    months = (today.year - year) * 12 + (today.month - month)
    if months < 1:
        months = 1
    return round(cited / months, 3)


def collect_openalex(
    technology_id: str,
    query: str,
    *,
    http: HttpGetter,
    expected_title: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Собрать сведения о публикации: площадка, рецензирование, цитирования.

    `query` — адрес arXiv, DOI либо название работы. Возвращает свидетельства
    типа `publication`; сведения о цитированиях попадают в поле значения, откуда
    их извлекает оркестратор для временного ряда.
    """
    today = today or date.today()
    result = CollectResult(source_name="openalex", technology_id=technology_id)

    work: dict | None = None

    arxiv_match = _ARXIV_RE.search(query)
    doi_match = _DOI_RE.search(query)
    if arxiv_match:
        # У препринтов arXiv есть канонический DOI: это самый надёжный ключ.
        doi = f"10.48550/arXiv.{arxiv_match.group('id')}"
        work = _get_json(http, _polite(f"{OPENALEX_API}/works/doi:{doi}"), result)
    elif doi_match:
        work = _get_json(http, _polite(f"{OPENALEX_API}/works/doi:{doi_match.group(0)}"), result)

    def _norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _title_of(candidate: dict) -> str:
        return (candidate.get("title") or candidate.get("display_name") or "").strip()

    # Название, по которому ищутся остальные версии работы. Разрешённое по
    # идентификатору название авторитетнее имени технологии: второе может
    # совпасть с посторонней работой.
    resolved_title = _title_of(work) if work else ""
    search_title = resolved_title or (expected_title or "")

    # Второй шаг: у препринта и у конференционной публикации разные записи, и
    # рецензирование видно только у второй.
    candidates: list[dict] = [work] if work else []
    if search_title:
        # В фильтре запятая и вертикальная черта разделяют условия, двоеточие
        # отделяет имя фильтра от значения, а вопросительный знак и звёздочка
        # означают подстановку. Названия работ содержат их сплошь и рядом —
        # «What Retrieval Granularity Should We Use?» ломало запрос кодом 400,
        # и работа молча оставалась без сведений о площадке.
        #
        # Разделители заменяются пробелом: поиск по словам от этого не
        # страдает, а запрос перестаёт быть недопустимым.
        safe_title = re.sub(r"[,|:?*]+", " ", search_title).strip()
        search = _get_json(
            http,
            _polite(f"{OPENALEX_API}/works?filter=title.search:{quote(safe_title)}&per_page=25"),
            result,
        )
        if search:
            candidates.extend(search.get("results") or [])
    elif not work:
        search = _get_json(
            http, _polite(f"{OPENALEX_API}/works?search={quote(query)}&per_page=25"), result
        )
        if search:
            candidates.extend(search.get("results") or [])

    if not candidates:
        if not result.errors:
            result.errors.append("OpenAlex: работа не найдена")
        return result

    # Отбор совпадений. Если работа разрешена по идентификатору, принимаются
    # только записи с тем же названием. Если нет — название технологии обязано
    # быть началом названия работы: «Self-RAG» подходит к «Self-RAG: Learning
    # to Retrieve...», но не к посторонней работе, где оно лишь упоминается.
    if resolved_title:
        wanted = _norm(resolved_title)
        matched = [c for c in candidates if _norm(_title_of(c)) == wanted]
    elif expected_title:
        wanted = _norm(expected_title)
        matched = [c for c in candidates if _norm(_title_of(c)).startswith(wanted)]
    else:
        matched = candidates[:1]

    if not matched:
        # Ненадёжное совпадение хуже отсутствия данных: неверная запись в
        # реестре разрушает доверие ко всем остальным.
        result.errors.append(
            f"OpenAlex: надёжного совпадения по названию не найдено "
            f"({search_title!r}); свидетельство не создано"
        )
        return result

    candidates = matched
    best = max(candidates, key=lambda c: c.get("cited_by_count") or 0)
    venue, peer_reviewed = "", False
    for candidate in candidates:
        name, reviewed = _venue_of(candidate)
        if reviewed:
            venue, peer_reviewed = name, True
            break
        venue = venue or name

    cited = best.get("cited_by_count") or 0
    year = best.get("publication_year") or ""
    velocity = _citation_velocity(best, today)

    value = (
        f"venue={venue or 'unknown'}; peer_reviewed={'true' if peer_reviewed else 'false'}; "
        f"cited_by={cited}; year={year}"
    )
    if velocity is not None:
        value += f"; citation_velocity={velocity}"

    # В свидетельство попадает название, по которому шло сопоставление, а не
    # имя технологии: последнее короче заголовка работы, и последующая проверка
    # сходства заголовков отвергала бы верные совпадения. Сама защита от чужой
    # работы обеспечена строгим отбором выше, а он жёстче сравнения по сходству.
    matched_title = _title_of(best)
    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value=value,
        source=best.get("id") or f"{OPENALEX_API}/works",
        fetched_at=today,
        obtained_by="auto",
        verified=False,
        expected_title=resolved_title or matched_title,
        actual_title=matched_title,
    ))
    return result
