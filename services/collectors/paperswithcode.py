"""Сборщик каталога Papers with Code: площадка публикации и обнаружение работ.

Каталог даёт две вещи, которых нет у прочих источников.

**Второй источник для уровня L2.** Площадка публикации приходила только из
открытого индекса работ, и его ошибка ничем не перекрывалась. Здесь она
приходит из каталога, который ведут люди. Данные о площадке разрежены: у
большинства препринтов её нет, и тогда свидетельство не создаётся. Это
правильно: отсутствие сведения не то же самое, что сведение об отсутствии.

**Ленту для обнаружения новых работ.** Метка метода в каталоге проставлена
людьми, и плотность сигнала от этого меняется на порядок: запрос по метке `rag`
за неделю даёт около пяти работ, тогда как полнотекстовый поиск в архиве
препринтов даёт около пятидесяти, и большинство из них приложения, а не
архитектуры. Пять кандидатов человек просматривает за минуту.

**Ответ проверяется на то, что он отвечает на заданный вопрос.** У каталога есть
параметры, которые он молча игнорирует: `q`, `arxiv_id`, `title`, `ordering`.
Обращение с ними отвечает кодом 200 и лентой свежайших работ всей области,
и такой ответ неотличим от осмысленного. Поэтому здесь проверяется, что
пришедшая работа имеет запрошенный идентификатор, а работы ленты не старше
запрошенной даты. Без этой проверки сборщик молча приписывал бы записям чужие
свидетельства.

Каталог ведёт сообщество при Hugging Face после закрытия paperswithcode.com.
Долговечность его не доказана, поэтому отказ каталога обрабатывается как отказ
любого другого источника: проход продолжается, отказ попадает в журнал.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

PWC_API = "https://paperswithcode.co/api/v1"

#: Метка метода, под которой каталог собирает работы про RAG.
RAG_METHOD = "rag"

#: Признаки рецензируемой площадки в поле сборника. Каталог пишет туда строку
#: вида «NeurIPS 2020 12», то есть имя площадки и год.
_VENUE_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class Paper:
    """Карточка работы в каталоге, приведённая к тому, что нужно порталу."""

    arxiv_id: str
    title: str
    #: Аннотация работы, как её даёт каталог. Своими словами пересказывать
    #: нечего: аннотация и есть краткое изложение, написанное авторами.
    abstract: str
    published: date | None
    venue: str | None
    citations: int | None
    url: str
    repositories: list[str] = field(default_factory=list)
    #: Метки задач каталога, проставленные людьми. По ним оценивается
    #: пригодность кандидата реестру, и они же позволяют пересчитать оценку
    #: без повторного обращения к каталогу.
    tasks: list[str] = field(default_factory=list)


def _paper_url(arxiv_id: str) -> str:
    return f"{PWC_API}/papers/{arxiv_id}"


def _get_json(http: HttpGetter, url: str) -> tuple[dict | None, str | None]:
    if not is_allowed_host(url):
        return None, f"домен вне allowlist: {url}"
    status, body = http.get(url, timeout=30)
    if status == 404:
        return None, None  # работы в каталоге нет — это ответ, а не сбой
    if status != 200:
        return None, f"код {status} от {url}"
    try:
        return json.loads(body), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"некорректный ответ от {url}"


def _as_date(value: object) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _venue_of(payload: dict) -> str | None:
    """Площадка публикации, если каталог её знает.

    Полей три, и заполнено обычно не больше одного. Пустое поле означает, что
    сведения нет, а не что работа не публиковалась: у Self-RAG, принятого на
    конференцию, здесь пусто.
    """
    for key in ("proceeding", "conference_name", "conference"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_paper(payload: dict) -> Paper | None:
    """Привести карточку каталога к виду, который нужен порталу."""
    arxiv_id = payload.get("arxiv_id")
    title = payload.get("title")
    if not isinstance(arxiv_id, str) or not isinstance(title, str):
        return None
    repos = payload.get("repositories")
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=payload.get("abstract") if isinstance(payload.get("abstract"), str) else "",
        published=_as_date(payload.get("published")),
        venue=_venue_of(payload),
        citations=(
            payload["citation_count"]
            if isinstance(payload.get("citation_count"), int)
            else None
        ),
        url=_paper_url(arxiv_id),
        repositories=[
            r.get("url") for r in repos
            if isinstance(r, dict) and isinstance(r.get("url"), str)
        ] if isinstance(repos, list) else [],
        tasks=[
            t.get("slug") for t in payload.get("tasks") or []
            if isinstance(t, dict) and isinstance(t.get("slug"), str)
        ],
    )


def fetch_paper(
    arxiv_id: str, *, http: HttpGetter
) -> tuple[Paper | None, str | None]:
    """Карточка работы по идентификатору препринта.

    Возвращает работу и причину отказа. Пришедшая работа обязана иметь именно
    запрошенный идентификатор: каталог отвечает лентой свежайших работ на
    обращения с игнорируемыми параметрами, и такой ответ выглядит осмысленным.
    """
    payload, error = _get_json(http, _paper_url(arxiv_id))
    if error or payload is None:
        return None, error
    paper = parse_paper(payload)
    if paper is None:
        return None, f"каталог вернул карточку без обязательных полей: {arxiv_id}"
    if paper.arxiv_id != arxiv_id:
        return None, (
            f"каталог ответил не о том, о чём спрошено: запрошен {arxiv_id}, "
            f"получен {paper.arxiv_id}"
        )
    return paper, None


def collect_venue(
    technology_id: str,
    arxiv_id: str,
    *,
    http: HttpGetter,
    today: date | None = None,
) -> CollectResult:
    """Свидетельство о площадке публикации из каталога.

    Число цитирований пишется в свидетельство, но **не** в ряд показателей.
    Внимание на карте нормируется внутри возрастной подгруппы, и подгруппа
    считается по одному счётчику; смешать два счётчика одной работы значило бы
    сравнивать несравнимое, а правило «берём наибольшее по источникам» ещё и
    систематически завышало бы результат. Счётчик назван в самом значении,
    чтобы читатель видел, чьё это число.
    """
    today = today or date.today()
    result = CollectResult(source_name="paperswithcode", technology_id=technology_id)

    paper, error = fetch_paper(arxiv_id, http=http)
    if error:
        result.errors.append(error)
        return result
    if paper is None:
        return result  # работы в каталоге нет
    if not paper.venue:
        # Сведения о площадке нет. Свидетельство типа «публикация» без неё
        # утверждало бы ровно то, что уже утверждает препринт.
        return result

    peer_reviewed = bool(_VENUE_YEAR.search(paper.venue))
    parts = [f"venue={paper.venue}", f"peer_reviewed={str(peer_reviewed).lower()}"]
    if paper.citations is not None:
        parts.append(f"citations_semantic_scholar={paper.citations}")
    if paper.published:
        parts.append(f"year={paper.published.year}")

    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="publication",
        value="; ".join(parts),
        source=paper.url,
        fetched_at=today,
        expected_title=None,
        actual_title=paper.title,
    ))
    return result


def discover(
    *,
    http: HttpGetter,
    published_after: date,
    method: str = RAG_METHOD,
) -> tuple[list[Paper], list[str]]:
    """Работы под меткой метода, вышедшие не раньше указанной даты.

    Возвращает найденное и причины отказов. Работы старше запрошенной даты
    отбрасываются вместе с объяснением: каталог молча игнорирует часть
    параметров, и лента свежайших работ всей области неотличима от ответа по
    существу. Пустая лента при этом законна: неделя без новых работ бывает.
    """
    query = urlencode({"method": method, "published_after": published_after.isoformat()})
    payload, error = _get_json(http, f"{PWC_API}/papers/?{query}")
    if error or payload is None:
        return [], [error] if error else []

    rows = payload.get("results")
    if not isinstance(rows, list):
        return [], [f"каталог вернул ленту без перечня работ: {type(rows).__name__}"]

    found: list[Paper] = []
    problems: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        paper = parse_paper(row)
        if paper is None:
            continue
        if paper.published is None:
            problems.append(f"работа без даты публикации: {paper.arxiv_id}")
            continue
        if paper.published < published_after:
            problems.append(
                f"каталог отдал работу от {paper.published.isoformat()} на запрос "
                f"от {published_after.isoformat()}: параметр даты не применён"
            )
            continue
        found.append(paper)
    return found, problems
