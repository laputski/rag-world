"""Чтение и запись файлового реестра.

Раскладка описана в `registry/README.md`. Коротко:

    data/technologies/<id>.json   факты, файл на запись
    data/evidence/YYYY-MM.jsonl   свидетельства, только добавление
    data/metrics/YYYY.jsonl       временные ряды показателей
    data/levels/history.jsonl     журнал изменений уровня

Свидетельства и показатели **только добавляются**: существующая строка никогда не
переписывается, поэтому любое значение уровня объяснимо набором свидетельств,
доступных на момент вычисления (принцип K6). Записи технологий, наоборот,
перезаписываются целиком, а история изменений остаётся в системе контроля версий.

Файлы записываются устойчиво: ключи объектов упорядочены, отступ фиксирован, в
конце перевод строки. Это делает различия между версиями читаемыми и не даёт
появляться шумным изменениям, за которыми не стоит содержания.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field

# Корень данных: каталог `data/` рядом с корнем репозитория.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

TECHNOLOGIES_DIR = DATA_DIR / "technologies"
EVIDENCE_DIR = DATA_DIR / "evidence"
METRICS_DIR = DATA_DIR / "metrics"
LEVELS_FILE = DATA_DIR / "levels" / "history.jsonl"

Kind = Literal["paradigm", "architecture", "technique", "tool", "artifact"]
LinkKind = Literal["paper", "preprint", "github", "product", "venue", "other"]
LinkStatus = Literal["verified", "needs_review", "unresolved"]
EvidenceType = Literal[
    "publication",
    "independent_reproduction",
    "repository",
    "build_run",
    "framework_presence",
    "package_downloads",
    "industrial_use",
    "provider_count",
]


class Link(BaseModel):
    """Разрешимый источник сведений о технологии."""

    model_config = ConfigDict(extra="forbid")

    url: str
    kind: LinkKind = "other"
    label: str | None = None
    status: LinkStatus = "needs_review"
    verified_at: date | None = None


class Technology(BaseModel):
    """Факты о технологии. Длинные тексты сюда не попадают (принцип K3)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    kind: Kind
    family: str | None = None
    #: Страты измерений A–G, к которым относится вклад технологии.
    groups: list[str] = Field(default_factory=list)
    #: Значения измерений — главное поле для сравнения технологий.
    configuration: dict[str, str] = Field(default_factory=dict)
    #: Механизмы, не выразимые схемой измерений.
    residual: list[str] = Field(default_factory=list)
    core_idea: str | None = None
    prose_id: str | None = None
    first_published: str | None = None
    links: list[Link] = Field(default_factory=list)


class Evidence(BaseModel):
    """Свидетельство в пользу уровня зрелости. Никогда не перезаписывается."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    type: EvidenceType
    value: str | None = None
    source: str
    fetched_at: date
    obtained_by: Literal["auto", "manual"] = "manual"
    verified: bool = False


class MetricPoint(BaseModel):
    """Точка временного ряда: цитирования, звёзды, загрузки пакета."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    metric: str
    value: float
    measured_at: date
    source: str


class LevelEntry(BaseModel):
    """Строка журнала уровней. Добавляется только при изменении уровня."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    level: str
    confidence: float
    #: `computed` — вычислено правилом; `manual` — введено человеком там, где
    #: машиночитаемого источника не существует.
    evidence_basis: Literal["computed", "manual"] = "computed"
    rule_version: str
    computed_at: date
    #: Свидетельства, учтённые при вычислении: тип и источник.
    evidence_snapshot: list[dict[str, str]] = Field(default_factory=list)


# ─── Служебное ───────────────────────────────────────────────────────────────


def _dump(model: BaseModel) -> str:
    """Каноническое представление записи: устойчивый порядок ключей."""
    return json.dumps(
        model.model_dump(mode="json", exclude_none=False),
        ensure_ascii=False,
        sort_keys=True,
    )


def _read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _append_jsonl(path: Path, models: Iterable[BaseModel]) -> int:
    rows = [_dump(m) for m in models]
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row + "\n")
    return len(rows)


# ─── Технологии ──────────────────────────────────────────────────────────────


def load_technologies() -> list[Technology]:
    """Все записи реестра, упорядоченные по идентификатору."""
    if not TECHNOLOGIES_DIR.exists():
        return []
    items = [
        Technology.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(TECHNOLOGIES_DIR.glob("*.json"))
    ]
    return sorted(items, key=lambda t: t.id)


def load_technology(tech_id: str) -> Technology | None:
    path = TECHNOLOGIES_DIR / f"{tech_id}.json"
    if not path.exists():
        return None
    return Technology.model_validate_json(path.read_text(encoding="utf-8"))


def save_technology(tech: Technology) -> Path:
    """Записать запись целиком. История изменений остаётся в системе версий."""
    TECHNOLOGIES_DIR.mkdir(parents=True, exist_ok=True)
    path = TECHNOLOGIES_DIR / f"{tech.id}.json"
    payload = json.dumps(
        tech.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    )
    path.write_text(payload + "\n", encoding="utf-8")
    return path


# ─── Свидетельства ───────────────────────────────────────────────────────────


def evidence_path(when: date) -> Path:
    """Помесячный раздел: закрытый месяц больше не переписывается."""
    return EVIDENCE_DIR / f"{when.year:04d}-{when.month:02d}.jsonl"


def load_evidence(technology_id: str | None = None) -> list[Evidence]:
    """Все свидетельства, при необходимости отобранные по технологии."""
    if not EVIDENCE_DIR.exists():
        return []
    out: list[Evidence] = []
    for path in sorted(EVIDENCE_DIR.glob("*.jsonl")):
        for row in _read_jsonl(path):
            item = Evidence.model_validate(row)
            if technology_id is None or item.technology_id == technology_id:
                out.append(item)
    return out


def append_evidence(items: Iterable[Evidence]) -> int:
    """Добавить свидетельства, разложив их по месяцам получения.

    Дубликаты по (технология, тип, источник, значение) отбрасываются: повторный
    прогон сборщиков не должен раздувать журнал.
    """
    items = list(items)
    if not items:
        return 0
    known = {
        (e.technology_id, e.type, e.source, e.value or "") for e in load_evidence()
    }
    by_month: dict[Path, list[Evidence]] = {}
    for item in items:
        key = (item.technology_id, item.type, item.source, item.value or "")
        if key in known:
            continue
        known.add(key)
        by_month.setdefault(evidence_path(item.fetched_at), []).append(item)
    return sum(_append_jsonl(path, rows) for path, rows in by_month.items())


# ─── Показатели ──────────────────────────────────────────────────────────────


def metrics_path(when: date) -> Path:
    return METRICS_DIR / f"{when.year:04d}.jsonl"


def load_metrics(technology_id: str | None = None) -> list[MetricPoint]:
    if not METRICS_DIR.exists():
        return []
    out: list[MetricPoint] = []
    for path in sorted(METRICS_DIR.glob("*.jsonl")):
        for row in _read_jsonl(path):
            item = MetricPoint.model_validate(row)
            if technology_id is None or item.technology_id == technology_id:
                out.append(item)
    return out


def append_metrics(points: Iterable[MetricPoint]) -> int:
    by_year: dict[Path, list[MetricPoint]] = {}
    for point in points:
        by_year.setdefault(metrics_path(point.measured_at), []).append(point)
    return sum(_append_jsonl(path, rows) for path, rows in by_year.items())


# ─── Уровни ──────────────────────────────────────────────────────────────────


def load_levels(technology_id: str | None = None) -> list[LevelEntry]:
    out = [LevelEntry.model_validate(row) for row in _read_jsonl(LEVELS_FILE)]
    if technology_id is not None:
        out = [e for e in out if e.technology_id == technology_id]
    return out


def latest_level(technology_id: str) -> LevelEntry | None:
    """Последняя запись журнала для технологии, либо None, если её нет.

    Отсутствие записи означает «уровень не вычислялся» и отличается от уровня L0:
    представления обязаны показывать это различие, а не подставлять ноль.
    """
    entries = load_levels(technology_id)
    return entries[-1] if entries else None


def append_level(entry: LevelEntry) -> bool:
    """Добавить запись, если уровень действительно изменился.

    Возвращает True, если запись добавлена. Пересчёт без изменения уровня журнал
    не трогает, поэтому он читается как хроника, а не как лог запусков.
    """
    previous = latest_level(entry.technology_id)
    if previous is not None and previous.level == entry.level:
        return False
    LEVELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl(LEVELS_FILE, [entry])
    return True
