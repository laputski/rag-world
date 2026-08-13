"""Обнаружение работ по курируемым тематическим спискам.

Каталог работ находит новое по меткам задач, и это его сила и его предел.
Метку ставит тот, кто выкладывает работу, поэтому каталог знает о работе ровно
то, что о ней заявили, и не знает, признали ли её своей те, кто в области
работает. Курируемый список знает обратное: он ничего не знает о метках, но
включение в него есть решение человека, разбирающегося в предмете.

Отсюда роль этого сборщика. Он не заменяет каталог, а добавляет второй, иначе
устроенный отбор: работа, попавшая в обзорный список по графовому извлечению,
признана своей сообществом, даже если в каталоге метка ей не проставлена.

Сборщик читает разметку списка и достаёт из неё **идентификаторы**, а сведения
о работе берёт у arXiv. Порядок именно такой и по существу: список пишут
руками, и доверять его формулировкам как источнику нельзя, тогда как
идентификатор проверяем и однозначен.

Записей сборщик не заводит: он пополняет очередь кандидатов, где решение
принимает человек, как и для прочих путей обнаружения.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from services.collectors.arxiv import ARXIV_API, _parse_atom_entries
from services.collectors.base import HttpGetter, is_allowed_host
from services.collectors.paperswithcode import Paper


@dataclass(frozen=True)
class CuratedList:
    """Курируемый список, из которого берутся идентификаторы работ."""

    #: Имя списка. Попадает в очередь кандидатов как происхождение находки.
    name: str
    #: Адрес разметки. Берётся сырой файл, а не страница: страница несёт
    #: оформление площадки, которое меняется независимо от содержания списка.
    readme: str
    #: Страница списка для читателя.
    page: str
    #: Обзор, по которому список составлен, если он есть.
    survey: str | None = None


#: Списки, которые опрашиваются.
#:
#: Перечень намеренно короткий. Курируемый список полезен ровно настолько,
#: насколько его ведёт человек, разбирающийся в предмете; список, собранный
#: ради числа звёзд, даёт шум, который потом разбирать руками.
CURATED_LISTS: tuple[CuratedList, ...] = (
    CuratedList(
        name="Awesome-GraphRAG",
        readme="https://raw.githubusercontent.com/DEEP-PolyU/Awesome-GraphRAG/main/README.md",
        page="https://github.com/DEEP-PolyU/Awesome-GraphRAG",
        survey="arXiv:2501.13958",
    ),
)

#: Строка записи в списке: род площадки в скобках, заголовок полужирным,
#: где-то дальше ссылка на препринт. Разбирается именно эта форма, а всё
#: прочее пропускается: попытка понять произвольную разметку кончается
#: выдуманными заголовками.
ENTRY = re.compile(
    r"^-\s*\((?P<venue>[^)]{1,60})\)\s*\*\*(?P<title>.+?)\*\*"
    r"(?P<tail>.*?)$",
    re.M,
)

ARXIV_LINK = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>[0-9]{4}\.[0-9]{4,5})")

#: Год в обозначении площадки: «(ICLR 2026)» даёт 2026.
VENUE_YEAR = re.compile(r"\b(19|20)(\d{2})\b")

#: Сколько идентификаторов запрашивается у arXiv за одно обращение.
#:
#: Ограничение вежливости, а не возможностей: arXiv принимает список через
#: запятую, и дробить его на отдельные запросы значит бить по чужой службе
#: без нужды.
BATCH = 25


@dataclass(frozen=True)
class ListedEntry:
    """Запись списка: то, что удалось прочитать из разметки, и не более."""

    arxiv_id: str
    title: str
    venue: str
    year: int | None


def parse_entries(markup: str) -> list[ListedEntry]:
    """Разобрать разметку списка в записи с идентификаторами препринтов.

    Функция чистая и не обращается к сети: разбор проверяется на записанной
    разметке, а не на том, что сегодня лежит в чужом репозитории.
    """
    entries: list[ListedEntry] = []
    seen: set[str] = set()
    for match in ENTRY.finditer(markup):
        link = ARXIV_LINK.search(match.group("tail"))
        if not link:
            # Запись без препринта пропускается молча: у работы может не быть
            # идентификатора вовсе, и это не поломка списка.
            continue
        arxiv_id = link.group("id")
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        venue = match.group("venue").strip()
        year = VENUE_YEAR.search(venue)
        entries.append(ListedEntry(
            arxiv_id=arxiv_id,
            title=re.sub(r"\s+", " ", match.group("title")).strip(),
            venue=venue,
            year=int(year.group(0)) if year else None,
        ))
    return entries


def _abstracts(
    http: HttpGetter, arxiv_ids: list[str]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Аннотации и даты работ по идентификаторам, пачками."""
    found: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for start in range(0, len(arxiv_ids), BATCH):
        chunk = arxiv_ids[start:start + BATCH]
        url = f"{ARXIV_API}?id_list={','.join(chunk)}&max_results={len(chunk)}"
        if not is_allowed_host(url):
            problems.append(f"домен вне перечня разрешённых: {url}")
            continue
        status, body = http.get(url, timeout=30)
        if status != 200:
            problems.append(f"arXiv вернул {status} на пачку из {len(chunk)} работ")
            continue
        for entry in _parse_atom_entries(body):
            # Идентификатор в ответе несёт номер версии; список его не знает.
            bare = entry["id"].split("v")[0]
            found[bare] = entry
    return found, problems


def discover_from_lists(
    *,
    http: HttpGetter,
    published_after: date | None = None,
    lists: tuple[CuratedList, ...] = CURATED_LISTS,
    known: set[str] | None = None,
) -> tuple[list[Paper], list[str]]:
    """Работы из курируемых списков, приведённые к общему виду кандидата.

    `known` содержит идентификаторы, о которых решение уже принято либо
    которые уже в реестре. Отсев по нему делается **до** обращения к arXiv:
    список содержит сотню с лишним работ, из которых новых единицы, и
    спрашивать аннотации по всем значило бы бить по чужой службе впустую.
    """
    known = known or set()
    papers: list[Paper] = []
    problems: list[str] = []

    for source in lists:
        if not is_allowed_host(source.readme):
            problems.append(f"домен вне перечня разрешённых: {source.readme}")
            continue
        status, body = http.get(source.readme, timeout=30)
        if status != 200:
            problems.append(f"{source.name}: разметка списка вернула {status}")
            continue
        try:
            markup = body.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(f"{source.name}: разметка не читается как UTF-8")
            continue

        entries = parse_entries(markup)
        if not entries:
            # Пустой разбор при успешном ответе означает, что список сменил
            # форму записи. Молчать нельзя: сборщик выглядел бы работающим.
            problems.append(
                f"{source.name}: разметка получена, но ни одной записи не разобрано; "
                "вероятно, изменилась форма списка"
            )
            continue

        fresh = [entry for entry in entries if entry.arxiv_id not in known]
        if published_after is not None:
            fresh = [
                entry for entry in fresh
                if entry.year is None or entry.year >= published_after.year
            ]
        if not fresh:
            continue

        details, trouble = _abstracts(http, [entry.arxiv_id for entry in fresh])
        problems.extend(f"{source.name}: {item}" for item in trouble)

        for entry in fresh:
            detail = details.get(entry.arxiv_id)
            if not detail:
                # Аннотации нет — кандидата нет. Оценивать пригодность по
                # одному заголовку значит выдавать догадку за измерение.
                problems.append(
                    f"{source.name}: arXiv не отдал работу {entry.arxiv_id}"
                )
                continue
            published = detail.get("published") or ""
            papers.append(Paper(
                arxiv_id=entry.arxiv_id,
                # Заголовок берётся у arXiv, а не из списка: список пишут
                # руками, и опечатка в нём разошлась бы по очереди кандидатов.
                title=detail.get("title") or entry.title,
                abstract=detail.get("summary", ""),
                published=date.fromisoformat(published) if len(published) == 10 else None,
                venue=entry.venue,
                citations=None,
                url=f"https://arxiv.org/abs/{entry.arxiv_id}",
                repositories=[],
                tasks=[],
            ))
    return papers, problems
