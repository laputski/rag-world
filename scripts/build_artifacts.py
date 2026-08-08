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
    public/data/feed.xml       лента хроники

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

#: Показатели, из которых выводится внимание и распространённость.
ATTENTION_METRIC = "citation_velocity"
PREVALENCE_METRICS = ("package_downloads", "repository_stars")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _latest_metric(points: list[store.MetricPoint], metric: str) -> float | None:
    relevant = [p for p in points if p.metric == metric]
    if not relevant:
        return None
    return max(relevant, key=lambda p: p.measured_at).value


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

    built_at = _now()
    freshest = max((e.fetched_at for e in evidence), default=None)
    stale = freshest is None or (date.today() - freshest) > STALE_AFTER

    # ─── Реестр ──────────────────────────────────────────────────────────────
    registry_rows = []
    for tech in technologies:
        entry = level_by_tech.get(tech.id)
        tech_metrics = metrics_by_tech.get(tech.id, [])
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
            "level": entry.level if entry else None,
            "confidence": entry.confidence if entry else None,
            "evidence_basis": entry.evidence_basis if entry else None,
            # Внимание нужно и ленте реестра: по нему идёт одна из сортировок.
            "attention": _latest_metric(tech_metrics, ATTENTION_METRIC),
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
        tech_metrics = metrics_by_tech.get(tech.id, [])
        prevalence = next(
            (
                value
                for value in (
                    _latest_metric(tech_metrics, m) for m in PREVALENCE_METRICS
                )
                if value is not None
            ),
            None,
        )
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
            "attention": _latest_metric(tech_metrics, ATTENTION_METRIC),
            "prevalence": prevalence,
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
    _write_feed(target / "feed.xml", changes, built_at)
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


def _write_feed(path: Path, changes: list[dict], built_at: str) -> None:
    """Лента хроники: свежесть, видимая снаружи без открытия портала."""
    items = []
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
