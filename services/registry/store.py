"""Reading and writing the file-based registry.

The layout is described in `docs/DATA.md`. In short::

    data/technologies/<id>.json   the facts, one file per record
    data/evidence/YYYY-MM.jsonl   evidence, append-only
    data/metrics/YYYY.jsonl       the measurement series
    data/levels/history.jsonl     the journal of level changes

Evidence and measurements are **appended only**: an existing line is never
rewritten, so any level is explicable by the evidence available when it was
computed. Technology records, by contrast, are rewritten whole, and the history
of their changes stays in version control.

Files are written stably: object keys are ordered, the indent is fixed, and
there is a newline at the end. That makes the difference between two versions
readable and keeps spurious changes with no content behind them from appearing.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field

# The root of the data: the `data/` directory beside the root of the repository.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

TECHNOLOGIES_DIR = DATA_DIR / "technologies"
EVIDENCE_DIR = DATA_DIR / "evidence"
METRICS_DIR = DATA_DIR / "metrics"
LEVELS_FILE = DATA_DIR / "levels" / "history.jsonl"
COLLECTION_LOG = DATA_DIR / "collection_log.jsonl"

#: The kind of an object. An attack stands apart: the other kinds describe RAG
#: systems or parts of them and therefore occupy a place in the configuration
#: space, whereas an attack acts **upon** such a system from outside. It has no
#: dimension values of its own, and base ones would assert that it segments
#: documents and searches for nearest neighbours, which it does not do.
Kind = Literal[
    "paradigm", "architecture", "technique", "tool", "artifact", "attack"
]

#: The kinds the configuration space does not apply to at all.
KINDS_WITHOUT_CONFIGURATION = frozenset({"attack"})
LinkKind = Literal["paper", "preprint", "github", "product", "venue", "other"]
#: The state of a source.
#:
#: `guarded` came about because without it a link had no way out of the state
#: "nobody looked". Publishers and some venues answer robots with a refusal on
#: rights, and such a refusal is deliberately not counted as the death of a
#: link: taking it for one would spoil the registry faster than time spoils
#: addresses. But then the address stayed in `needs_review` for ever,
#: indistinguishable from one nobody had looked at, and nobody learned of it.
#:
#: `guarded` asserts something checkable: the request was made, the address
#: answered, and it declined to show itself to a robot. Only a person can
#: confirm it.
LinkStatus = Literal["verified", "needs_review", "unresolved", "guarded"]
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
    """A resolvable source of information about a technology."""

    model_config = ConfigDict(extra="forbid")

    url: str
    kind: LinkKind = "other"
    label: str | None = None
    #: The English label of the link. It is filled in only where the label is
    #: written in Russian: an address and a preprint number need no translation.
    label_en: str | None = None
    status: LinkStatus = "needs_review"
    verified_at: date | None = None


class Technology(BaseModel):
    """The facts about a technology. Long texts do not belong here."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    kind: Kind
    family: str | None = None
    #: The strata A–G the technology's contribution belongs to.
    groups: list[str] = Field(default_factory=list)
    #: The dimension values, the field two technologies are compared by.
    configuration: dict[str, str] = Field(default_factory=dict)
    #: Mechanisms the schema does not express, as codes from the residual
    #: vocabulary (`data/residual_vocabulary.json`). Free text is inadmissible:
    #: counting repetitions is possible only when the wording coincides.
    residual: list[str] = Field(default_factory=list)
    #: Dimensions whose value the system chooses while running or according to
    #: its mode. The value written down is the one from the fullest branch, and
    #: this mark says it is not the only one. Without it, a comparison treats
    #: the record as occupying a single cell and the gap map declares the
    #: neighbouring cells empty although the system occupies them too.
    configuration_variable: list[str] = Field(default_factory=list)
    #: Dimensions inapplicable to the object: a retriever has no synthesis
    #: stage, so "generation is single-pass" asserts something about what does
    #: not exist. Such dimensions carry no value in `configuration` at all: an
    #: absent value and a base value are different assertions, exactly as an
    #: absent level and the level L0 are.
    configuration_inapplicable: list[str] = Field(default_factory=list)
    #: The date the configuration was read out of the sources. Empty means the
    #: record was never read and its base values assert nothing. Filled in means
    #: the values were checked against the primary source, those coinciding with
    #: the base ones included: "it matches the base configuration" and "nobody
    #: looked" are different assertions, and without this date the gap map would
    #: show the second as the first.
    configuration_reviewed: date | None = None
    prose_id: str | None = None
    first_published: str | None = None
    #: The name of the package in the Python package index, when one exists. It
    #: is filled in by a person: it cannot be derived from the technology's name,
    #: and guessing is worse still — somebody else's package with a similar name
    #: would yield false evidence.
    package: str | None = None
    links: list[Link] = Field(default_factory=list)


class Evidence(BaseModel):
    """Evidence for a maturity level. It is never rewritten."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    type: EvidenceType
    value: str | None = None
    #: The English wording of the value. It is needed where a person wrote the
    #: value: values collected automatically arrive in English from the source.
    value_en: str | None = None
    source: str
    fetched_at: date
    obtained_by: Literal["auto", "manual"] = "manual"
    verified: bool = False


class MetricPoint(BaseModel):
    """A point of a series: citations, stars, package downloads."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    metric: str
    value: float
    measured_at: date
    source: str


class CollectionRun(BaseModel):
    """A record of a collection pass. It appears always, even when nothing changed.

    It serves three purposes at once. It distinguishes "the data is old because
    nobody looked" from "the data is old because nothing happened", without
    which a reader cannot judge freshness. It gives the platform a sign of
    activity: a schedule is disabled after sixty days without commits, and a
    line of this journal is a commit. And it shows which sources answered and
    which did not.
    """

    model_config = ConfigDict(extra="forbid")

    ran_at: date
    #: The sources polled: arxiv, openalex, github, pypi, frameworks.
    sources: list[str] = Field(default_factory=list)
    evidence_added: int = 0
    metrics_added: int = 0
    levels_changed: int = 0
    #: How many requests to sources yielded nothing.
    source_errors: int = 0
    #: How many registry addresses were checked, and how many had vanished.
    links_checked: int = 0
    links_broken: int = 0
    #: Whether the registry data changed; if not, the artefacts are not rebuilt.
    data_changed: bool = False


class LevelEntry(BaseModel):
    """A line of the level journal. It is added only when the level changes."""

    model_config = ConfigDict(extra="forbid")

    technology_id: str
    level: str
    confidence: float
    #: `computed` means the rule produced it; `manual` means a person entered it
    #: where no machine-readable source exists.
    evidence_basis: Literal["computed", "manual"] = "computed"
    rule_version: str
    computed_at: date
    #: The evidence the computation took into account: type and source.
    evidence_snapshot: list[dict[str, str]] = Field(default_factory=list)


# ─── Internals ───────────────────────────────────────────────────────────────


def _dump(model: BaseModel) -> str:
    """The canonical form of a record: a stable order of keys."""
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


# ─── Technologies ────────────────────────────────────────────────────────────


def load_technologies() -> list[Technology]:
    """Every record of the registry, ordered by identifier."""
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
    """Write a record whole. The history of its changes stays in version control."""
    TECHNOLOGIES_DIR.mkdir(parents=True, exist_ok=True)
    path = TECHNOLOGIES_DIR / f"{tech.id}.json"
    payload = json.dumps(
        tech.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    )
    path.write_text(payload + "\n", encoding="utf-8")
    return path


# ─── Evidence ────────────────────────────────────────────────────────────────


def evidence_path(when: date) -> Path:
    """A partition by month: a closed month is never rewritten again."""
    return EVIDENCE_DIR / f"{when.year:04d}-{when.month:02d}.jsonl"


def load_evidence(technology_id: str | None = None) -> list[Evidence]:
    """All the evidence, filtered by technology when one is given."""
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
    """Append evidence, filed by the month it was fetched in.

    Duplicates by technology, type, source and value are dropped: a second run
    of the collectors must not inflate the journal.
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


# ─── Measurements ────────────────────────────────────────────────────────────


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
    """Append points of a series, dropping a repeated measurement of one day.

    Without this the weekly pass would append the same quantity on every run:
    the series would grow while carrying nothing new, and the bot would commit
    noise.

    The source is part of the key, and that matters. A record may have several
    works, and each yields **its own** citation velocity: a key without the
    source would collapse different measurements into one and lose all but the
    first. The value, on the contrary, is not part of the key — otherwise a
    repeated measurement of the same source on the same day would pass as a new
    point, and that is exactly the noise.
    """
    points = list(points)
    if not points:
        return 0

    def key(m: MetricPoint) -> tuple[str, str, str, str]:
        return (m.technology_id, m.metric, m.measured_at.isoformat(), m.source)

    known = {key(m) for m in load_metrics()}
    by_year: dict[Path, list[MetricPoint]] = {}
    for point in points:
        if key(point) in known:
            continue
        known.add(key(point))
        by_year.setdefault(metrics_path(point.measured_at), []).append(point)
    return sum(_append_jsonl(path, rows) for path, rows in by_year.items())


# ─── Levels ──────────────────────────────────────────────────────────────────


def load_levels(technology_id: str | None = None) -> list[LevelEntry]:
    out = [LevelEntry.model_validate(row) for row in _read_jsonl(LEVELS_FILE)]
    if technology_id is not None:
        out = [e for e in out if e.technology_id == technology_id]
    return out


def latest_level(technology_id: str) -> LevelEntry | None:
    """The last journal entry for a technology, or None when there is none.

    An absent entry means the level was never computed, which differs from the
    level L0: the views must show that difference rather than substitute a zero.
    """
    entries = load_levels(technology_id)
    return entries[-1] if entries else None


def load_runs() -> list[CollectionRun]:
    """The journal of collection passes, oldest first."""
    return [CollectionRun.model_validate(row) for row in _read_jsonl(COLLECTION_LOG)]


def latest_run() -> CollectionRun | None:
    runs = load_runs()
    return runs[-1] if runs else None


def append_run(run: CollectionRun) -> None:
    """Append a record of a pass. This happens always, changes or no changes."""
    COLLECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl(COLLECTION_LOG, [run])


def append_level(entry: LevelEntry) -> bool:
    """Append an entry when the level has actually changed.

    Returns True when an entry was added. A recomputation that changed nothing
    leaves the journal untouched, so it reads as a chronicle rather than a log
    of runs.
    """
    previous = latest_level(entry.technology_id)
    if previous is not None and previous.level == entry.level:
        return False
    LEVELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl(LEVELS_FILE, [entry])
    return True
