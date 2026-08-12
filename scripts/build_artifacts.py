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

#: Схема измерений для интерфейса порождается из той же декларации, что и для
#: остального кода. Переписать её вручную значило бы завести второе описание —
#: ровно то, что проект однажды уже пережил.
SCHEMA_MODULE = (
    Path(__file__).resolve().parent.parent / "ui" / "src" / "schema.generated.ts"
)

LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

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
    pending = [row for row in rows if not row.get("verdict")]
    return sorted(pending, key=lambda r: (r.get("published") or "", r["arxiv_id"]),
                  reverse=True)


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
        "strata": [{"code": code, "name": name} for code, name in STRATA.items()],
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
    by_level = Counter(
        (level_by_tech[t.id].level if t.id in level_by_tech else "unknown")
        for t in technologies
    )
    by_stratum: Counter[str] = Counter()
    for tech in technologies:
        for group in tech.groups:
            by_stratum[group] += 1

    stats = {
        "built_at": built_at,
        "total": len(technologies),
        "by_level": dict(sorted(by_level.items())),
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
    _write_feed(target / "feed.xml", changes, built_at, _issues())
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
    path: Path, changes: list[dict], built_at: str, issues: list[dict] | None = None
) -> None:
    """Лента: выпуски дайджеста и изменения уровней.

    Выпуски идут первыми: читателю ленты нужно сообщение о происходящем, а
    отдельные изменения уровня — его подробность.
    """
    items = []
    for issue in (issues or [])[:20]:
        items.append(
            "    <item>\n"
            f"      <title>{escape('Дайджест за ' + issue['issued_at'])}</title>\n"
            f"      <description>{escape(issue.get('text', ''))}</description>\n"
            f"      <guid isPermaLink=\"false\">digest-{escape(issue['issued_at'])}</guid>\n"
            "    </item>"
        )
    for change in changes[:50]:
        title = f"{change['name']}: {change['level_before'] or '—'} → {change['level_after']}"
        body = ", ".join(
            f"{e.get('type', '')} {e.get('source', '')}".strip()
            for e in change["evidence"][:5]
        ) or "основание не указано"
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
        "    <title>RAG World: хроника изменений</title>\n"
        "    <description>Изменения уровней зрелости технологий RAG</description>\n"
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
