#!/usr/bin/env python3
"""Сборка артефактов, которые читает портал.

Портал статический: он не обращается к реестру во время работы, а читает
заранее собранные файлы. Отсюда следует свойство, ради которого всё и сделано:
отказ внешнего источника приводит к устареванию данных, а не к отказу портала
(принцип K5).

Собираются:

    public/data/registry.json  реестр целиком; отбор идёт на клиенте
    public/data/map.json       точки карты зрелости
    public/data/changes.json   хроника изменений со ссылками на свидетельства
    public/data/stats.json     сводка: распределение, покрытие, свежесть
    public/data/digest.json    выпуски дайджеста, свежие впереди
    public/data/residuals.json  очередь остатков: чего схема не выражает
    public/data/candidates.json очередь кандидатов: чего нет в реестре
    public/data/feed.xml       лента: выпуски и изменения уровней

Ни одно число не попадает в артефакт без происхождения: внимание и
распространённость берутся из временных рядов, а если ряда нет, поле остаётся
пустым и представление обязано показать «нет данных», а не ноль.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dimensions_schema import DIMENSIONS, SCHEMA_SIZE, STRATA  # noqa: E402
from core.maturity import RULE_VERSION, EvidenceIn, compute_level  # noqa: E402
from services.registry import store  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "ui" / "public" / "data"

#: Постоянный адрес портала. Входит в машиночитаемое описание и в карту сайта,
#: поэтому задан здесь один раз, а не повторяется по файлам.
SITE = "https://ragworld.org"

#: Хранилище исходных данных. Клонирование остаётся первым способом доступа:
#: артефакты производны, а история изменений живёт только в нём.
REPOSITORY = "https://github.com/laputski/rag-world"

#: Лицензия на данные и артефакты; та же, что в data/LICENSE.md.
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_NAME = "CC BY 4.0"

#: Страницы портала, существующие постоянно. Карточки технологий добавляются к
#: ним по реестру, поэтому карта сайта не отстаёт от него на новую запись.
STATIC_ROUTES = ("/", "/registry", "/changes", "/digest", "/residuals",
                 "/article", "/about")

#: Схема измерений для интерфейса порождается из той же декларации, что и для
#: остального кода. Переписать её вручную значило бы завести второе описание —
#: ровно то, что проект однажды уже пережил.
SCHEMA_MODULE = (
    Path(__file__).resolve().parent.parent / "ui" / "src" / "schema.generated.ts"
)

LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

#: Подписи ленты по языкам. Лента объявляет язык на канал целиком, поэтому
#: перевод здесь не пара полей, а второй канал со своими подписями.
FEED_WORDS = {
    "en": {
        "title": "RAG World: chronicle of changes",
        "description": "Maturity level changes for RAG technologies",
        "digest": "Digest for",
        "none": "none",
        "noBasis": "no basis recorded",
    },
    "ru": {
        "title": "RAG World: хроника изменений",
        "description": "Изменения уровней зрелости технологий RAG",
        "digest": "Дайджест за",
        "none": "нет",
        "noBasis": "основание не указано",
    },
}

#: Данные считаются устаревшими, если самое свежее свидетельство старше этого
#: срока. Признак показывается в интерфейсе всегда.
STALE_AFTER = timedelta(days=45)

#: Показатель, из которого выводится внимание.
#:
#: Распространённости на карте нет, и это решение, а не упущение. Точка карты
#: несла поле `prevalence`, задававшее её размер, но заполнить его было нечем:
#: ряд с такими показателями никто не писал, поэтому размер у всех шестидесяти
#: двух точек был одинаков, а поле молча оставалось пустым.
#:
#: Заполнить его честно не выходит. Загрузки пакета есть у семи записей из
#: шестидесяти двух и различаются в тридцать тысяч раз, от полутора тысяч в
#: месяц до пятидесяти двух миллионов. По прежней формуле все семь упирались в
#: наибольший размер, а прочие пятьдесят пять получали размер «нет данных»,
#: неотличимый от размера «скачивают редко»: величина превращалась в признак
#: «есть пакет на Python». Вдобавок наибольшие загрузки принадлежат
#: OpenSearch и Qdrant, то есть общему инструменту, а не приёму RAG, и карта
#: утверждала бы их первенство в предметной области.
#:
#: Звёзд репозитория не собирает никто, поэтому вторая половина правила
#: описывала источник, которого нет. Складывать же загрузки со звёздами нельзя
#: и по существу: это разные величины в разных единицах.
ATTENTION_METRIC = "citation_velocity"


def _built_at() -> str:
    """Момент, на который собраны данные, а не момент запуска скрипта.

    Различие существенно для еженедельного прогона. Если брать часы, артефакты
    отличаются при каждом запуске даже когда ничего не изменилось, и бот
    коммитит шум, в котором тонет настоящая хроника. Дата выводится из самих
    данных: свежайшее свидетельство, изменение уровня либо показатель.

    Ответ на вопрос «когда проверяли в последний раз» даёт журнал прогонов —
    он для того и заведён.
    """
    stamps: list[str] = []
    stamps += [e.fetched_at.isoformat() for e in store.load_evidence()]
    stamps += [e.computed_at.isoformat() for e in store.load_levels()]
    stamps += [m.measured_at.isoformat() for m in store.load_metrics()]
    if not stamps:
        # Данных нет вовсе: дата берётся от часов, иначе её неоткуда взять.
        return datetime.now(timezone.utc).date().isoformat()
    return max(stamps)


def _latest_metric(points: list[store.MetricPoint], metric: str) -> float | None:
    """Свежайшее измерение показателя по записи.

    У записи может быть несколько работ, и каждая измеряется отдельно. Свежесть
    поэтому считается **по каждому источнику отдельно**, а уже потом источники
    сводятся вместе. Порядок существенен, и обратный порядок портит данные.

    Сначала брали свежайшую дату по всей записи, а внутри неё наибольшее
    значение. Достаточно было одному источнику не ответить в очередной прогон,
    и он выпадал из расчёта целиком: свежайшая дата принадлежала уже другому
    источнику. Так у Dense X внимание упало с 1,089 до 0,101 не потому, что
    работу перестали цитировать, а потому, что вторую её работу в тот день не
    удалось опросить. Для прогона без человека это худший вид поломки: число
    меняется в десять раз и выглядит как наблюдение.

    Источники сводятся наибольшим значением, и этот выбор тоже не произволен:

    * брать первый попавшийся нельзя — величина зависела бы от порядка строк в
      файле, то есть от того, какая ссылка попала в запись раньше;
    * складывать нельзя — препринт и его конференционная версия существуют в
      индексе как две работы, и сумма посчитала бы одну работу дважды.

    Наибольшее — это внимание к самой заметной работе записи. Оно не
    завышается: такое измерение действительно существует.
    """
    relevant = [p for p in points if p.metric == metric]
    if not relevant:
        return None
    by_source: dict[str, store.MetricPoint] = {}
    for point in relevant:
        known = by_source.get(point.source)
        if known is None or (point.measured_at, point.value) > (
            known.measured_at, known.value
        ):
            by_source[point.source] = point
    return max(p.value for p in by_source.values())


#: Проза карточек: краткая суть и развёрнутое описание каждой записи.
#:
#: Тексты живут в ресурсах локализации портала, потому что пишутся вместе с
#: ним и правятся чаще данных. В артефакт они переносятся копией: реестр,
#: выгруженный наружу, состоял из кодов, уровней и ссылок без единого
#: предложения о том, что это за технология, и прочитать его без портала было
#: нельзя. Переносятся оба языка сразу, иначе выгрузка оказывается наполовину
#: на языке, которого потребитель не знает.
PROSE_DIR = Path(__file__).resolve().parent.parent / "ui" / "src" / "i18n"

#: Поле прозы и имя, под которым оно выходит в артефакт. Краткая суть
#: называется `summary`, а не `short`: за пределами интерфейса «короткое» не
#: говорит, короткое что.
PROSE_FIELDS = (
    ("short", "summary"),
    ("full", "description"),
    ("problem", "problem"),
    ("barriers", "barriers"),
    ("solutions", "solutions"),
    ("maturityNote", "maturity_note"),
)


def _prose() -> dict[str, dict[str, str]]:
    """Проза по записям на обоих языках, готовая к укладке в артефакт."""
    tables = {
        language: json.loads(
            (PROSE_DIR / language / "tech.json").read_text(encoding="utf-8")
        )
        for language in ("ru", "en")
    }
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for prose_id in tables["ru"]:
        for source_field, published in PROSE_FIELDS:
            russian = tables["ru"].get(prose_id, {}).get(source_field)
            english = tables["en"].get(prose_id, {}).get(source_field)
            if russian:
                out[prose_id][published] = russian
            if english:
                out[prose_id][f"{published}_en"] = english
    return dict(out)


def _strata_rows() -> list[dict]:
    """Страты с названиями на обоих языках.

    Названия берутся из ресурсов интерфейса, а не из схемы: в схеме они только
    русские, и артефакт получал бы половину подписи. Буквенная приставка вида
    «A. » снимается, потому что код страты стоит рядом отдельным полем.
    """
    names = {
        language: json.loads(
            (PROSE_DIR / f"{language}.json").read_text(encoding="utf-8")
        )["stratum"]
        for language in ("ru", "en")
    }
    strip = lambda label: label.split(". ", 1)[-1]  # noqa: E731
    return [
        {
            "code": code,
            "name": strip(names["ru"].get(code, russian)),
            "name_en": strip(names["en"].get(code, code)),
        }
        for code, russian in STRATA.items()
    ]


def _parse_notes() -> dict[str, list[dict]]:
    """Обоснования разбора по записям.

    Конфигурация — единственная часть портала, где решение принял человек, а не
    правило. У уровня показан вывод правила, у свидетельства — источник; без
    обоснования значение измерения остаётся утверждением, которое читателю
    нечем проверить, и оно же — самое субъективное на карточке.
    """
    path = store.DATA_DIR / "parse_notes.jsonl"
    if not path.exists():
        return {}
    notes: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            note = json.loads(line)
            notes[note["technology_id"]].append(note)
    return notes


def _candidate_queue() -> list[dict]:
    """Кандидаты, ждущие решения, свежие впереди.

    Решённые в очередь не попадают: принятый кандидат уже стал записью реестра,
    отклонённый записан в файл отклонений с причиной. Показывать их значило бы
    выдавать сделанную работу за несделанную.
    """
    path = store.DATA_DIR / "candidates.jsonl"
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pending = []
    for row in rows:
        if row.get("verdict"):
            continue
        # Аннотация обрезается для показа: она нужна читателю, чтобы решить,
        # стоит ли открывать работу, а целиком остаётся в данных. Обрыв идёт
        # по границе предложения, иначе фраза ломается на полуслове.
        abstract = (row.get("abstract") or "").strip()
        if len(abstract) > CANDIDATE_ABSTRACT_LIMIT:
            cut = abstract[:CANDIDATE_ABSTRACT_LIMIT]
            stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            abstract = (cut[: stop + 1] if stop > 200 else cut.rstrip() + "…")
        pending.append({**row, "abstract": abstract})
    # Порядок по оценке пригодности: очередь существует ради просмотра, и
    # смотреть надо сначала на то, что вероятнее подойдёт. При равной оценке
    # впереди свежее.
    return sorted(
        pending,
        key=lambda r: ((r.get("fit") or {}).get("score", 0),
                       r.get("published") or "", r["arxiv_id"]),
        reverse=True,
    )


#: Сколько знаков аннотации показывать. Двух-трёх предложений хватает, чтобы
#: понять, о чём работа; целиком аннотация открывается по ссылке на источник.
CANDIDATE_ABSTRACT_LIMIT = 480


def _residual_vocabulary() -> dict[str, dict]:
    path = store.DATA_DIR / "residual_vocabulary.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in payload.get("mechanisms", [])}


def _residual_term(code: str, lang: str = "ru") -> str:
    """Формулировка механизма остатка по его коду.

    Неизвестный код возвращается как есть: проверка данных такую запись не
    пропустит, а сборка не должна молча превращать ошибку в пустое место.
    """
    entry = _residual_vocabulary().get(code)
    return entry.get(lang, code) if entry else code


#: Со скольких упоминаний механизм остатка считается кандидатом в измерение
#: схемы. Три — не магия, а разумный минимум: один случай бывает у любой
#: работы, два могут оказаться совпадением, а три раза подряд схема
#: промахивается уже не случайно.
RESIDUAL_CANDIDATE_THRESHOLD = 3


def _residual_queue(technologies: list[store.Technology]) -> list[dict]:
    """Механизмы остатка с числом упоминаний и записями, где они встретились.

    Смысл очереди в том, что схема должна расти от наблюдений, а не от
    воображения. Механизм, который приходится записывать в остаток снова и
    снова, — это место, где схема мала; механизм, встреченный однажды, —
    частность конкретной работы.
    """
    vocabulary = _residual_vocabulary()
    seen: dict[str, list[dict]] = defaultdict(list)
    for tech in technologies:
        for code in tech.residual:
            seen[code].append({"id": tech.id, "name": tech.name})

    rows = []
    for code, users in seen.items():
        entry = vocabulary.get(code, {})
        rows.append({
            "id": code,
            "term": entry.get("ru", code),
            "term_en": entry.get("en", code),
            "note": entry.get("note", ""),
            "note_en": entry.get("note_en", entry.get("note", "")),
            "count": len(users),
            "technologies": sorted(users, key=lambda u: u["name"]),
            "candidate": len(users) >= RESIDUAL_CANDIDATE_THRESHOLD,
        })
    return sorted(rows, key=lambda r: (-r["count"], r["term"]))


#: Ниже этого размера возрастная подгруппа не нормируется: медиана по трём
#: значениям неустойчива и сдвигается от появления одной новой работы сильнее,
#: чем от происходящего в области.
MIN_COHORT = 5


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def attention_cohorts(
    technologies: list[store.Technology],
    metrics_by_tech: dict[str, list[store.MetricPoint]],
) -> dict[str, float]:
    """Медиана скорости цитирования по году первой публикации.

    Сравнивать скорости напрямую нельзя: работа двухлетней давности набирает
    цитирования дольше, чем вышедшая позавчера, и без нормировки старое всегда
    выглядит популярнее нового. Нормировка внутри возрастной подгруппы этот
    перекос снимает.
    """
    by_year: dict[str, list[float]] = defaultdict(list)
    for tech in technologies:
        if not tech.first_published:
            continue
        value = _latest_metric(
            metrics_by_tech.get(tech.id, []), ATTENTION_METRIC
        )
        if value is not None:
            by_year[tech.first_published[:4]].append(value)
    return {
        year: _median(values)
        for year, values in by_year.items()
        if len(values) >= MIN_COHORT and _median(values) > 0
    }


def normalized_attention(
    tech: store.Technology,
    metrics_by_tech: dict[str, list[store.MetricPoint]],
    cohorts: dict[str, float],
) -> dict[str, object]:
    """Внимание в трёх видах: измеренное, нормированное и происхождение.

    Возвращаются все три, потому что каждое отвечает на свой вопрос. Читателю
    показывается нормированное, но происхождение обязано быть доступно, а без
    сырого значения его не проверить.
    """
    raw = _latest_metric(metrics_by_tech.get(tech.id, []), ATTENTION_METRIC)
    if raw is None:
        return {"attention": None, "attention_raw": None, "attention_cohort": None}

    year = (tech.first_published or "")[:4]
    median = cohorts.get(year)
    if median is None:
        # Подгруппа мала либо год неизвестен: нормировать нечем. Показывается
        # измеренное значение с пометкой, а не выдуманное нормированное.
        return {
            "attention": raw,
            "attention_raw": raw,
            "attention_cohort": None,
        }
    return {
        "attention": round(raw / median, 3),
        "attention_raw": raw,
        "attention_cohort": year,
    }


def build(out_dir: Path | None = None) -> dict[str, int]:
    """Собрать артефакты. `out_dir` подменяется в проверке на расхождение."""
    technologies = store.load_technologies()
    evidence = store.load_evidence()
    levels = store.load_levels()
    metrics = store.load_metrics()

    evidence_by_tech: dict[str, list[store.Evidence]] = defaultdict(list)
    for item in evidence:
        evidence_by_tech[item.technology_id].append(item)

    metrics_by_tech: dict[str, list[store.MetricPoint]] = defaultdict(list)
    for point in metrics:
        metrics_by_tech[point.technology_id].append(point)

    level_by_tech: dict[str, store.LevelEntry] = {}
    history_by_tech: dict[str, list[store.LevelEntry]] = defaultdict(list)
    for entry in levels:
        level_by_tech[entry.technology_id] = entry  # журнал упорядочен по времени
        history_by_tech[entry.technology_id].append(entry)

    cohorts = attention_cohorts(technologies, metrics_by_tech)
    parse_notes = _parse_notes()
    prose = _prose()

    built_at = _built_at()
    freshest = max((e.fetched_at for e in evidence), default=None)
    stale = freshest is None or (date.today() - freshest) > STALE_AFTER

    # ─── Реестр ──────────────────────────────────────────────────────────────
    registry_rows = []
    for tech in technologies:
        entry = level_by_tech.get(tech.id)
        tech_evidence = evidence_by_tech.get(tech.id, [])

        # Вывод правила прилагается к записи, чтобы карточка могла показать,
        # почему уровень такой и чего не хватает до следующего. Без этого
        # уровень остаётся утверждением, которое читателю нечем проверить.
        reasoning = None
        if tech_evidence:
            result = compute_level([
                EvidenceIn(
                    type=e.type, source=e.source, value=e.value,
                    fetched_at=e.fetched_at, verified=e.verified,
                )
                for e in tech_evidence
            ])
            reasoning = {
                "satisfied": result.satisfied,
                "missing": result.missing,
                "confidence": round(result.confidence, 3),
                "evidence_basis": result.evidence_basis,
            }

        registry_rows.append({
            **tech.model_dump(mode="json"),
            **prose.get(tech.prose_id or "", {}),
            # Данные хранят код механизма, читателю нужна формулировка.
            # Подстановка на сборке, а не в реестре: тогда перевод словаря не
            # требует переписывать записи технологий.
            "residual": [_residual_term(code) for code in tech.residual],
            "residual_en": [_residual_term(code, "en") for code in tech.residual],
            # Обоснование разбора: почему у измерения такое значение. Остаток
            # получает формулировку из словаря, чтобы карточка не показывала код.
            "parse_notes": [
                {
                    **note,
                    "residual_term": (
                        _residual_term(note["residual"]) if note.get("residual") else None
                    ),
                    "residual_term_en": (
                        _residual_term(note["residual"], "en")
                        if note.get("residual") else None
                    ),
                }
                for note in parse_notes.get(tech.id, [])
            ],
            "level": entry.level if entry else None,
            "confidence": entry.confidence if entry else None,
            "evidence_basis": entry.evidence_basis if entry else None,
            # Внимание нужно и ленте реестра: по нему идёт одна из сортировок.
            **normalized_attention(tech, metrics_by_tech, cohorts),
            "evidence_count": len(tech_evidence),
            "evidence": [
                {
                    "type": e.type,
                    "value": e.value,
                    "value_en": e.value_en,
                    "source": e.source,
                    "fetched_at": e.fetched_at.isoformat(),
                    "obtained_by": e.obtained_by,
                }
                for e in tech_evidence
            ],
            "level_reason": reasoning,
        })

    # ─── Карта ───────────────────────────────────────────────────────────────
    points = []
    for tech in technologies:
        entry = level_by_tech.get(tech.id)
        points.append({
            "id": tech.id,
            "name": tech.name,
            "kind": tech.kind,
            # Первый страт определяет цвет; полный набор нужен для отбора.
            "group": tech.groups[0] if tech.groups else None,
            "groups": tech.groups,
            # Отсутствие уровня остаётся отсутствием: подставлять L0 нельзя,
            # иначе «не изучено» становится неотличимо от «гипотеза».
            "level": entry.level if entry else None,
            "confidence": entry.confidence if entry else None,
            "evidence_basis": entry.evidence_basis if entry else None,
            **normalized_attention(tech, metrics_by_tech, cohorts),
            "first_published": tech.first_published,
            "prose_id": tech.prose_id,
            # История нужна карте для показа движения за период: без неё
            # свежесть данных остаётся утверждением, а не наблюдением.
            "history": [
                {"level": h.level, "at": h.computed_at.isoformat()}
                for h in history_by_tech.get(tech.id, [])
            ],
        })

    map_artifact = {
        "built_at": built_at,
        "rule_version": RULE_VERSION,
        "levels": LEVELS,
        "strata": _strata_rows(),
        "points": points,
        "count": len(points),
        "stale": stale,
    }

    # ─── Хроника ─────────────────────────────────────────────────────────────
    order = {level: i for i, level in enumerate(LEVELS)}
    previous: dict[str, str] = {}
    changes = []
    names = {t.id: t.name for t in technologies}
    for entry in levels:
        before = previous.get(entry.technology_id)
        if before is None:
            kind = "added"
        elif order.get(entry.level, 0) > order.get(before, 0):
            kind = "level_up"
        else:
            kind = "level_down"
        previous[entry.technology_id] = entry.level
        changes.append({
            "technology_id": entry.technology_id,
            "name": names.get(entry.technology_id, entry.technology_id),
            "kind": kind,
            "level_before": before,
            "level_after": entry.level,
            "evidence": entry.evidence_snapshot,
            "changed_at": entry.computed_at.isoformat(),
        })
    changes.sort(key=lambda c: c["changed_at"], reverse=True)

    # ─── Сводка ──────────────────────────────────────────────────────────────
    # Уровни перечисляются все, включая пустые.
    #
    # Счётчик заводил ключ только там, где запись нашлась, поэтому L6 из сводки
    # выпадал целиком: шкала выглядела кончающейся на L5, тогда как «ни одна
    # технология не достигла отраслевого стандарта» есть, пожалуй, самое
    # содержательное её утверждение.
    #
    # Правилу «ноль вместо отсутствия недопустим» это не противоречит: ноль
    # здесь и есть наблюдение, а «не знаем» живёт отдельным ключом `unknown`.
    counted = Counter(
        (level_by_tech[t.id].level if t.id in level_by_tech else "unknown")
        for t in technologies
    )
    by_level = {level: counted.get(level, 0) for level in LEVELS}
    by_level["unknown"] = counted.get("unknown", 0)
    by_stratum: Counter[str] = Counter()
    for tech in technologies:
        for group in tech.groups:
            by_stratum[group] += 1

    stats = {
        "built_at": built_at,
        "total": len(technologies),
        "by_level": by_level,
        "by_kind": dict(sorted(Counter(t.kind for t in technologies).items())),
        "by_stratum": dict(sorted(by_stratum.items())),
        "with_evidence": sum(1 for t in technologies if evidence_by_tech.get(t.id)),
        "with_level": len(level_by_tech),
        "with_attention": sum(1 for p in points if p["attention"] is not None),
        "evidence_total": len(evidence),
        "freshest_evidence": freshest.isoformat() if freshest else None,
        "stale": stale,
    }

    # ─── Запись ──────────────────────────────────────────────────────────────
    target = out_dir or OUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "registry.json", {
        "built_at": built_at,
        "count": len(registry_rows),
        "technologies": registry_rows,
    })
    _write(target / "map.json", map_artifact)
    _write(target / "changes.json", {"built_at": built_at, "changes": changes})
    _write(target / "stats.json", stats)
    # Выпуски дайджеста — данные, а не производное: они дозаписываются
    # отдельным шагом и здесь только перекладываются для чтения порталом,
    # свежими вперёд.
    _write(target / "digest.json", {"built_at": built_at, "issues": _issues()})
    # Очередь кандидатов: работы, найденные каталогом и ждущие решения
    # человека. Обнаружение записей не заводит, поэтому кандидат остаётся
    # предположением, пока владелец не примет его либо не отклонит.
    _write(target / "candidates.json", {
        "built_at": built_at,
        "candidates": _candidate_queue(),
    })
    _write(target / "residuals.json", {
        "built_at": built_at,
        "candidate_threshold": RESIDUAL_CANDIDATE_THRESHOLD,
        "mechanisms": _residual_queue(technologies),
    })
    # Лента односоставна по устройству: язык объявляется на канал целиком.
    # Поэтому языков две ленты, а не одна с полями на двух языках.
    # Запись реестра отдельным файлом.
    #
    # Карточка технологии читала весь реестр ради одной записи: восемьсот
    # килобайт на страницу, куда чаще всего и приходят по ссылке извне. Файл на
    # запись стоит около десяти килобайт, а состав его тот же, поэтому
    # потребитель, которому нужна одна технология, не платит за остальные.
    per_record = target / "tech"
    per_record.mkdir(parents=True, exist_ok=True)
    stale = {path.name for path in per_record.glob("*.json")}
    for row in registry_rows:
        _write(per_record / f"{row['id']}.json", {"built_at": built_at, "technology": row})
        stale.discard(f"{row['id']}.json")
    # Запись, удалённая из реестра, не должна остаться отдаваемой по ссылке.
    for name in stale:
        (per_record / name).unlink()

    _write_feed(target / "feed.xml", changes, built_at, _issues(), "en")
    _write_feed(target / "feed.ru.xml", changes, built_at, _issues(), "ru")
    # Машиночитаемый вход: описание набора данных, карта сайта и указатель для
    # языковых моделей. Собираются здесь, потому что зависят от тех же чисел,
    # что и артефакты, и врозь с ними разошлись бы на первой же новой записи.
    _write(target / "index.json", _access_manifest(target, built_at, registry_rows, stats))
    _write_sitemap(target.parent / "sitemap.xml", registry_rows, built_at)
    (target.parent / "llms.txt").write_text(
        render_llms_txt(built_at, registry_rows, stats), encoding="utf-8"
    )
    if out_dir is None:
        SCHEMA_MODULE.write_text(render_schema_module(), encoding="utf-8")

    return {
        "technologies": len(registry_rows),
        "points": len(points),
        "changes": len(changes),
        "with_level": len(level_by_tech),
    }


def render_schema_module() -> str:
    """Модуль TypeScript со схемой измерений, порождённый из декларации."""
    strata = ",\n".join(
        f'  {{ code: "{code}", name: {json.dumps(name, ensure_ascii=False)} }}'
        for code, name in STRATA.items()
    )
    dimensions = ",\n".join(
        "  {{ code: \"{code}\", name: {name}, stratum: \"{stratum}\", "
        "core: {core}, default: \"{default}\", values: {values} }}".format(
            code=d.code,
            name=json.dumps(d.name, ensure_ascii=False),
            stratum=d.group,
            core="true" if d.core else "false",
            default=d.default,
            values=json.dumps(list(d.values), ensure_ascii=False),
        )
        for d in DIMENSIONS
    )
    return (
        "// СГЕНЕРИРОВАНО из core/dimensions_schema.py командой `make artifacts`.\n"
        "// Не править вручную: правка потеряется и разведёт два описания схемы.\n"
        "\n"
        "export interface DimensionSpec {\n"
        "  code: string;\n"
        "  name: string;\n"
        "  stratum: string;\n"
        "  core: boolean;\n"
        "  default: string;\n"
        "  values: string[];\n"
        "}\n"
        "\n"
        f"export const SCHEMA_SIZE = {SCHEMA_SIZE};\n"
        "\n"
        "export const STRATA: { code: string; name: string }[] = [\n"
        f"{strata},\n"
        "];\n"
        "\n"
        "export const DIMENSIONS: DimensionSpec[] = [\n"
        f"{dimensions},\n"
        "];\n"
        "\n"
        "/** Коды измерений страты в порядке объявления. */\n"
        "export function dimensionsOf(stratum: string): DimensionSpec[] {\n"
        "  return DIMENSIONS.filter((d) => d.stratum === stratum);\n"
        "}\n"
    )


#: Наборы данных, публикуемые порталом: файл, ключ с записями и назначение.
#:
#: Описания по-английски намеренно. Их читает не посетитель, а тот, кто
#: подключает набор к своей системе, и в этой роли английский общий.
DATASETS: tuple[tuple[str, str, str], ...] = (
    ("registry.json", "technologies",
     "Every technology in the registry with its configuration over the 28 "
     "dimensions, maturity level, the rule output behind that level, and the "
     "evidence records the level stands on."),
    ("map.json", "points",
     "Maturity level against attention for every record, as plotted on the "
     "maturity map."),
    ("changes.json", "changes",
     "Append-only chronicle: every level change with its date and the "
     "evidence that caused it."),
    ("stats.json", "",
     "Counts by kind, level, and stratum, plus the date of the freshest "
     "evidence."),
    ("residuals.json", "mechanisms",
     "Mechanisms recorded as not expressible in the current schema, with the "
     "records that raised each one. Three mentions make a mechanism a "
     "candidate for a new dimension."),
    ("candidates.json", "candidates",
     "Works found by weekly discovery and awaiting a human verdict, each with "
     "a deterministic fit score from 0 to 10."),
    ("digest.json", "issues",
     "Digest issues, generated from the chronicle without a language model."),
)


def _access_manifest(target: Path, built_at: str, rows: list[dict], stats: dict) -> dict:
    """Описание набора данных для машинного потребителя.

    Артефакты лежали в открытом каталоге и раньше, но узнать об их
    существовании можно было только прочитав исходный код портала. Указатель
    называет каждый набор, его назначение и число записей в нём, поэтому
    подключение не требует ни разбора страниц, ни чтения кода.

    Число записей берётся из только что записанных файлов, а не из переменных
    сборки. Так указатель описывает опубликованное, а не задуманное, и
    разойтись с ним не может.
    """
    datasets = []
    for name, key, description in DATASETS:
        entry: dict = {
            "url": f"{SITE}/data/{name}",
            "description": description,
        }
        if key:
            payload = json.loads((target / name).read_text(encoding="utf-8"))
            entry["records_at"] = key
            entry["records"] = len(payload.get(key, []))
        datasets.append(entry)

    return {
        "name": "RAG World",
        "site": SITE,
        "built_at": built_at,
        "license": {"name": LICENSE_NAME, "url": LICENSE_URL},
        "attribution": f"RAG World, {SITE}",
        "repository": REPOSITORY,
        "documentation": f"{SITE}/about",
        "schema": {
            "dimensions": SCHEMA_SIZE,
            "strata": _strata_rows(),
            "levels": LEVELS,
            "rule_version": RULE_VERSION,
        },
        "technologies": len(rows),
        "technology_ids": sorted(row["id"] for row in rows),
        "datasets": datasets,
        # Запись по одной: адрес собирается подстановкой обозначения. Читателю
        # набора это нужнее полного перечня из шестидесяти девяти адресов.
        "technology": {
            "url_template": f"{SITE}/data/tech/{{id}}.json",
            "description": "One registry record on its own, in the same shape as "
                           "a row of registry.json. Use it when a single "
                           "technology is wanted: the full registry costs "
                           "eighty times more.",
        },
        # Выпуски неизменны: ссылка на запись внутри выпуска указывает на то,
        # что не изменится, тогда как ссылка на текущий артефакт указывает на
        # движущийся объект. Для цитирования годится только первое.
        "releases": f"{SITE}/data/releases/index.json",
        # Ленты названы по языкам: канал объявляет язык целиком, поэтому их
        # две, и потребителю нужно знать, какая на каком.
        "feeds": {
            "en": f"{SITE}/data/feed.xml",
            "ru": f"{SITE}/data/feed.ru.xml",
        },
        "sitemap": f"{SITE}/sitemap.xml",
    }


def _write_sitemap(path: Path, rows: list[dict], built_at: str) -> None:
    """Карта сайта по постоянным страницам и карточкам реестра."""
    day = built_at[:10]
    urls = [f"{SITE}{route}" for route in STATIC_ROUTES]
    urls += [f"{SITE}/tech/{row['id']}" for row in sorted(
        rows, key=lambda r: r["id"]
    )]
    body = "\n".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{day}</lastmod></url>"
        for url in urls
    )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n",
        encoding="utf-8",
    )


def render_llms_txt(built_at: str, rows: list[dict], stats: dict) -> str:
    """Указатель портала для языковых моделей.

    Соглашение llmstxt.org: короткий файл в корне, из которого видно, что на
    сайте есть и где это лежит в машиночитаемом виде. Смысл его в том, чтобы
    модель, которой нужны сведения о технологиях RAG, брала их из набора
    данных, а не разбирала страницы: разбор страниц даёт худшие сведения и
    ломается при первой же правке вёрстки.
    """
    lines = [
        "# RAG World",
        "",
        "> A self-updating registry of retrieval-augmented generation "
        "technologies. Every record carries a configuration over a 28-dimension "
        "schema, a maturity level from L0 to L6 derived by a deterministic rule "
        "with no language model involved, and the evidence that level stands on. "
        "Data is collected weekly from arXiv, OpenAlex, GitHub, PyPI and Papers "
        "with Code.",
        "",
        "Do not scrape the pages. Every page on this site is rendered from the "
        "JSON files below, and those files are the same data without the markup. "
        f"Start from {SITE}/data/index.json, which lists them all.",
        "",
        f"- Records: {len(rows)}",
        f"- Evidence records: {stats.get('evidence_total')}",
        f"- Freshest evidence: {stats.get('freshest_evidence')}",
        f"- Built: {built_at}",
        f"- Licence: {LICENSE_NAME}, {LICENSE_URL}",
        f"- Attribution: RAG World, {SITE}",
        "",
        "## Data",
        "",
        f"- [Index of all datasets]({SITE}/data/index.json): what each file "
        "holds, how many records, where the schema is described.",
    ]
    for name, _key, description in DATASETS:
        title = name.removesuffix(".json").replace("_", " ").capitalize()
        lines.append(f"- [{title}]({SITE}/data/{name}): {description}")
    lines += [
        "",
        "## Citing",
        "",
        f"- [Releases]({SITE}/data/releases/index.json): dated, immutable "
        "snapshots. Cite a release, not the live file: the live file changes "
        "every week.",
        f"- [How to cite]({SITE}/about): citation formats and the licence.",
        "",
        "## Source",
        "",
        f"- [Repository]({REPOSITORY}): the data lives in git as one JSON file "
        "per technology, plus append-only evidence and level journals. Cloning "
        "gives the full history; the artefacts above are derived from it.",
        "",
    ]
    return "\n".join(lines)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _issues() -> list[dict]:
    """Выпуски дайджеста, свежие впереди."""
    directory = store.DATA_DIR / "digest"
    if not directory.exists():
        return []
    issues = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
    return sorted(issues, key=lambda i: i["issued_at"], reverse=True)


def _write_feed(
    path: Path, changes: list[dict], built_at: str,
    issues: list[dict] | None = None, language: str = "en",
) -> None:
    """Лента: выпуски дайджеста и изменения уровней.

    Выпуски идут первыми: читателю ленты нужно сообщение о происходящем, а
    отдельные изменения уровня служат его подробностью.

    Лента односоставна по устройству: язык объявляется на канал целиком, и
    класть в один канал поля на двух языках нельзя. Поэтому выпускается две
    ленты, `feed.xml` по-английски и `feed.ru.xml` по-русски, а язык каждой
    объявлен в разметке, чтобы читалка не гадала.
    """
    words = FEED_WORDS[language]
    items = []
    for issue in (issues or [])[:20]:
        text = issue.get("text_en" if language == "en" else "text") or issue.get("text", "")
        items.append(
            "    <item>\n"
            f"      <title>{escape(words['digest'] + ' ' + issue['issued_at'])}</title>\n"
            f"      <description>{escape(text)}</description>\n"
            f"      <guid isPermaLink=\"false\">digest-{escape(issue['issued_at'])}</guid>\n"
            "    </item>"
        )
    for change in changes[:50]:
        before = change["level_before"] or words["none"]
        title = f"{change['name']}: {before} > {change['level_after']}"
        body = ", ".join(
            f"{e.get('type', '')} {e.get('source', '')}".strip()
            for e in change["evidence"][:5]
        ) or words["noBasis"]
        items.append(
            "    <item>\n"
            f"      <title>{escape(title)}</title>\n"
            f"      <description>{escape(body)}</description>\n"
            f"      <guid isPermaLink=\"false\">{escape(change['technology_id'])}"
            f"-{escape(change['changed_at'])}-{escape(change['level_after'])}</guid>\n"
            "    </item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{escape(words['title'])}</title>\n"
        f"    <description>{escape(words['description'])}</description>\n"
        f"    <language>{language}</language>\n"
        f"    <link>{SITE}/changes</link>\n"
        f"    <lastBuildDate>{escape(built_at)}</lastBuildDate>\n"
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )
    path.write_text(feed, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    counts = build()
    print(
        f"Артефакты собраны: технологий {counts['technologies']}, "
        f"точек карты {counts['points']}, записей хроники {counts['changes']}, "
        f"с вычисленным уровнем {counts['with_level']}"
    )
    print(f"Каталог: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
