"""Слой доступа к данным реестра технологий (ADR-010).

Чистый CRUD поверх psycopg без ORM. Модели — services/db/models.py. Сырые SQL
запросы; типы приводятся psycopg3 (JSONB ↔ dict, ARRAY(enum) ↔ list[str],
DATE ↔ date).

Идемпотентные upsert-операции используются скриптом-сидом (seed_db.py), чтобы
повторные запуски обновляли, а не дублировали.
"""

from __future__ import annotations

from typing import Iterable

from services.db import connection as db
from services.db.models import (
    Evidence,
    IsFuture,
    Link,
    LinkKind,
    LinkStatus,
    MeasurementGroup,
    TechnologyFull,
    TechnologyKind,
    TechnologySummary,
)

# ─── technologies ─────────────────────────────────────────────────────────────

_TECH_COLUMNS = """
    id, name, aliases, kind, family, tier, is_future,
    core_idea, prose_id, configuration, residual, notes,
    created_at, updated_at
"""


def _row_to_summary(row: tuple, groups: list[str]) -> TechnologySummary:
    (
        tid, name, aliases, kind, family, tier, is_future,
        core_idea, prose_id, configuration, residual, _notes,
        _created, _updated,
    ) = row
    return TechnologySummary(
        id=tid,
        name=name,
        aliases=list(aliases or []),
        kind=TechnologyKind(kind),
        family=family,
        tier=tier,
        groups=[MeasurementGroup(g) for g in (groups or [])],
        is_future=IsFuture(is_future),
        core_idea=core_idea,
        prose_id=prose_id,
        configuration=configuration or {},
        residual=list(residual or []),
    )


def list_technologies(
    *,
    kind: str | None = None,
    group: str | None = None,
    is_future: str | None = None,
    family: str | None = None,
) -> list[TechnologySummary]:
    """Список технологий с фильтрами (для реестра, радара, матрицы)."""
    where = []
    params: list = []
    if kind:
        where.append("t.kind = %s")
        params.append(kind)
    if is_future:
        where.append("t.is_future = %s")
        params.append(is_future)
    if family:
        where.append("t.family = %s")
        params.append(family)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.fetch_all(
        f"""
        SELECT {_TECH_COLUMNS}
        FROM technologies t
        {where_sql}
        ORDER BY t.name
        """,
        tuple(params),
    )
    if not rows:
        return []

    ids = [r[0] for r in rows]
    groups_map = _load_groups_for(ids)
    return [_row_to_summary(r, groups_map.get(r[0], [])) for r in rows]


def _load_groups_for(tech_ids: list[str]) -> dict[str, list[str]]:
    if not tech_ids:
        return {}
    rows = db.fetch_all(
        """
        SELECT technology_id, group_code
        FROM technology_groups
        WHERE technology_id = ANY(%s)
        """,
        (tech_ids,),
    )
    result: dict[str, list[str]] = {}
    for tid, g in rows:
        result.setdefault(tid, []).append(g)
    return result


def get_technology(tech_id: str) -> TechnologyFull | None:
    """Полная запись по id (включая links) для карточки технологии."""
    row = db.fetch_one(
        f"SELECT {_TECH_COLUMNS} FROM technologies t WHERE id = %s",
        (tech_id,),
    )
    if row is None:
        return None
    groups = _load_groups_for([tech_id]).get(tech_id, [])
    summary = _row_to_summary(row, groups)
    links = list_links(tech_id)
    return TechnologyFull(**summary.model_dump(), links=links)


def find_by_name_or_alias(name: str) -> str | None:
    """Дедупликация: возвращает id существующей записи по name или alias."""
    row = db.fetch_one(
        """
        SELECT id FROM technologies
        WHERE name = %s OR %s = ANY(aliases)
        """,
        (name, name),
    )
    return row[0] if row else None


def upsert_technology(
    *,
    id: str,
    name: str,
    kind: str,
    groups: list[str],
    aliases: list[str] | None = None,
    family: str | None = None,
    tier: int | None = None,
    is_future: str = "false",
    core_idea: str | None = None,
    prose_id: str | None = None,
    configuration: dict[str, str] | None = None,
    residual: list[str] | None = None,
    notes: str | None = None,
) -> None:
    """Идемпотентная вставка/обновление технологии.

    Используется сидом. Группы и алиасы заменяются целиком. При смене kind
    на paradigm tier обязателен (CHECK на уровне БД).
    """
    import json

    db.execute(
        """
        INSERT INTO technologies
            (id, name, aliases, kind, family, tier, is_future,
             core_idea, prose_id, configuration, residual, notes)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name            = EXCLUDED.name,
            aliases         = EXCLUDED.aliases,
            kind            = EXCLUDED.kind,
            family          = EXCLUDED.family,
            tier            = EXCLUDED.tier,
            is_future       = EXCLUDED.is_future,
            core_idea       = EXCLUDED.core_idea,
            prose_id        = EXCLUDED.prose_id,
            configuration   = EXCLUDED.configuration,
            residual        = EXCLUDED.residual,
            notes           = EXCLUDED.notes
        """,
        (
            id,
            name,
            list(aliases or []),
            kind,
            family,
            tier,
            is_future,
            core_idea,
            prose_id,
            json.dumps(configuration or {}),
            list(residual or []),
            notes,
        ),
    )
    _replace_groups(id, groups)


def _replace_groups(tech_id: str, groups: Iterable[str]) -> None:
    db.execute("DELETE FROM technology_groups WHERE technology_id = %s", (tech_id,))
    groups = list(groups)
    if not groups:
        return
    # По одному INSERT — триггеров/правил нет, объём малый.
    for g in groups:
        db.execute(
            "INSERT INTO technology_groups (technology_id, group_code) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (tech_id, g),
        )


# ─── links ────────────────────────────────────────────────────────────────────


def list_links(tech_id: str) -> list[Link]:
    rows = db.fetch_all(
        """
        SELECT id, technology_id, url, kind, label, status, verified_at
        FROM links WHERE technology_id = %s ORDER BY id
        """,
        (tech_id,),
    )
    return [
        Link(
            id=r[0],
            technology_id=r[1],
            url=r[2],
            kind=LinkKind(r[3]),
            label=r[4],
            status=LinkStatus(r[5]),
            verified_at=r[6],
        )
        for r in rows
    ]


def upsert_link(
    *,
    technology_id: str,
    url: str,
    kind: str,
    label: str | None = None,
    status: str = "needs_review",
    verified_at: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO links (technology_id, url, kind, label, status, verified_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (technology_id, url, kind) DO UPDATE SET
            label       = EXCLUDED.label,
            status      = EXCLUDED.status,
            verified_at = EXCLUDED.verified_at
        """,
        (technology_id, url, kind, label, status, verified_at),
    )


# ─── evidence ─────────────────────────────────────────────────────────────────


def list_evidence(tech_id: str) -> list[Evidence]:
    rows = db.fetch_all(
        """
        SELECT id, technology_id, type, value, source, fetched_at, obtained_by, verified
        FROM evidence WHERE technology_id = %s ORDER BY fetched_at, id
        """,
        (tech_id,),
    )
    from services.db.models import EvidenceType

    return [
        Evidence(
            id=r[0],
            technology_id=r[1],
            type=EvidenceType(r[2]),
            value=r[3],
            source=r[4],
            fetched_at=r[5],
            obtained_by=r[6],
            verified=r[7],
        )
        for r in rows
    ]


def add_evidence(
    *,
    technology_id: str,
    type: str,
    source: str,
    value: str | None = None,
    fetched_at: str,
    obtained_by: str = "manual",
    verified: bool = False,
) -> None:
    """Добавление свидетельства. Append-only: дубликат (по UNIQUE) молча игнорируется."""
    db.execute(
        """
        INSERT INTO evidence (technology_id, type, value, source, fetched_at, obtained_by, verified)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (technology_id, type, source, value) DO NOTHING
        """,
        (technology_id, type, value, source, fetched_at, obtained_by, verified),
    )


# ─── подсчёт ──────────────────────────────────────────────────────────────────


def count_technologies() -> int:
    row = db.fetch_one("SELECT count(*) FROM technologies")
    return int(row[0]) if row else 0


# ─── maturity_history: журнал версий уровня (02-AC-2) ─────────────────────────


def record_maturity(
    *,
    technology_id: str,
    level: str,
    confidence: float,
    rule_version: str,
    evidence_basis: str = "computed",
    evidence_snapshot: list[int] | None = None,
    computed_at: str | None = None,
) -> int:
    """Записать результат вычисления уровня в журнал (каждый расчёт — новая строка).

    Возвращает id новой записи maturity_history. Уровень на дату воспроизводим
    выборкой из журнала (замена git-воспроизводимости при переходе на БД).
    """
    import json

    row = db.fetch_one(
        """
        INSERT INTO maturity_history
            (technology_id, level, confidence, evidence_basis, rule_version,
             computed_at, evidence_snapshot)
        VALUES (%s, %s, %s, %s, %s, COALESCE(%s, now()), %s)
        RETURNING id
        """,
        (
            technology_id,
            level,
            confidence,
            evidence_basis,
            rule_version,
            computed_at,
            json.dumps(evidence_snapshot or []),
        ),
    )
    return int(row[0]) if row else 0


def latest_maturity(technology_id: str) -> tuple[str, float, str] | None:
    """Последний записанный уровень (level, confidence, rule_version) или None."""
    row = db.fetch_one(
        """
        SELECT level, confidence, rule_version
        FROM maturity_history
        WHERE technology_id = %s
        ORDER BY computed_at DESC, id DESC
        LIMIT 1
        """,
        (technology_id,),
    )
    if row is None:
        return None
    return (row[0], float(row[1]), row[2])


def maturity_at(technology_id: str, as_of: str) -> tuple[str, float] | None:
    """Уровень технологии на указанную дату (ISO-строка) — воспроизводимость 02-AC-2."""
    row = db.fetch_one(
        """
        SELECT level, confidence
        FROM maturity_history
        WHERE technology_id = %s AND computed_at <= %s::timestamptz
        ORDER BY computed_at DESC, id DESC
        LIMIT 1
        """,
        (technology_id, as_of),
    )
    if row is None:
        return None
    return (row[0], float(row[1]))


# ─── radar.json: артефакт радара зрелости (STAGE-7 Ф5, план 03 §3) ───────────

_LEVEL_ORDER = ["L6", "L5", "L4", "L3", "L2", "L1", "L0"]  # зрелые ближе к центру

# 7 равных колец фиксированной ширины. Структура шкалы не зависит от данных:
# L6 в центре, L0 на краю, каждое кольцо одной толщины. Плотные кольца
# решаются зумом в UI, а не искажением шкалы.
_RING_WIDTH = 10.0 / 7.0  # ~1.43 на кольцо
_RING_BOUNDS: list[tuple[float, float]] = [
    (i * _RING_WIDTH, (i + 1) * _RING_WIDTH) for i in range(7)
]


def build_radar_artifact() -> dict:
    """Собрать radar.json для радара зрелости (план 03 §3.1).

    Геометрия (03-8): угол и радиус точки вычисляются детерминированно, чтобы
    положение не менялось между выпусками без содержательной причины. Точки
    распределяются равномерно по дуге своего сектора на своём кольце, со
    стабильным сдвигом по радиусу внутри кольца. Это устраняет наложение точек
    и сохраняет стабильность позиции. Кольца нелинейны: внутренние (зрелые)
    шире, чтобы растущему числу зрелых технологий было место.

    Артефакт несёт ring_bounds и sector_bounds, чтобы UI рисовал границы колец
    и секторов и подписи групп без догадок о геометрии (единственный источник
    правды — backend). Читается UI (MaturityRadar) и обновляется конвейером S9.
    """
    import hashlib
    from datetime import datetime, timezone

    items = list_technologies()
    levels = _LEVEL_ORDER  # L6..L0 (индекс = ring)
    groups = ["A", "B", "C", "D", "E", "F", "G"]
    n_groups = len(groups)
    sector_angle = 2 * 3.141592653589793 / n_groups

    # Группируем точки по (group, level), чтобы распределить каждую группу
    # равномерно по своей дуге. Сортировка внутри группы по id делает порядок
    # детерминированным (стабильность позиции, 03-8).
    cells: dict[tuple[str, str], list] = {}
    for it in items:
        level_row = latest_maturity(it.id)
        level = level_row[0] if level_row else "L0"
        confidence = level_row[1] if level_row else 0.0
        primary_group = it.groups[0].value if it.groups else "A"
        if primary_group not in groups:
            primary_group = "A"
        cells.setdefault((primary_group, level), []).append({
            "id": it.id,
            "name": it.name,
            "kind": it.kind.value,
            "group": primary_group,
            "groups": [g.value for g in it.groups],
            "level": level,
            "confidence": round(confidence, 3),
            "is_future": it.is_future.value,
            "prose_id": it.prose_id,
        })

    points = []
    for (group, level), bucket in cells.items():
        bucket.sort(key=lambda p: p["id"])
        n = len(bucket)
        ring = levels.index(level) if level in levels else 6
        lo, hi = _RING_BOUNDS[ring]
        gi = groups.index(group)
        sector_center = (gi + 0.5) * sector_angle
        for i, p in enumerate(bucket):
            if n == 1:
                t = 0.5
            else:
                t = (i + 1) / (n + 1)
            angle = sector_center + (t - 0.5) * sector_angle * 0.85
            h = int(hashlib.sha256(p["id"].encode()).hexdigest(), 16)
            width = hi - lo
            radius_offset = ((h % 1000) / 1000.0 - 0.5) * width * 0.6
            p["angle"] = round(angle, 5)
            p["radius"] = round(lo + width / 2 + radius_offset, 5)
            p["ring"] = ring
            points.append(p)

    # Сортируем по kind для стабильного порядка серий в легенде.
    kind_order = {"paradigm": 0, "architecture": 1, "technique": 2, "tool": 3, "artifact": 4}
    points.sort(key=lambda p: (kind_order.get(p["kind"], 9), p["id"]))

    # Границы колец и секторов — UI рисует по ним разделители и подписи.
    ring_bounds = [
        {"level": lvl, "lo": round(lo, 3), "hi": round(hi, 3), "mid": round((lo + hi) / 2, 3)}
        for lvl, (lo, hi) in zip(levels, _RING_BOUNDS)
    ]
    sector_bounds = [
        {"group": g, "center": round((i + 0.5) * sector_angle, 5),
         "lo": round(i * sector_angle, 5), "hi": round((i + 1) * sector_angle, 5)}
        for i, g in enumerate(groups)
    ]

    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule_version": "1.0.0",
        "levels": levels,  # L6..L0 (центр..край)
        "groups": groups,
        "ring_bounds": ring_bounds,
        "sector_bounds": sector_bounds,
        "points": points,
        "count": len(points),
        # stale=False: артефакт собран сейчас. Конвейер S9 помечает stale=True,
        # если данные не обновлялись дольше периода актуальности (план 03 §3.2).
        "stale": False,
    }
