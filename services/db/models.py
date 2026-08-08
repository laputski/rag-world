"""Pydantic-модели записей реестра технологий (ADR-010/011).

Соответствуют таблицам services/db/migrations/001_registry.sql. Используются
слоем доступа (services/db/repository.py) и API (services/api/routers/registry.py).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TechnologyKind(str, Enum):
    PARADIGM = "paradigm"
    ARCHITECTURE = "architecture"
    TECHNIQUE = "technique"
    TOOL = "tool"
    ARTIFACT = "artifact"


class MeasurementGroup(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class IsFuture(str, Enum):
    TRUE = "true"
    FALSE = "false"
    BOTH = "both"


class LinkKind(str, Enum):
    PAPER = "paper"
    PREPRINT = "preprint"
    GITHUB = "github"
    PRODUCT = "product"
    VENUE = "venue"
    OTHER = "other"


class LinkStatus(str, Enum):
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    UNRESOLVED = "unresolved"


class Link(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    technology_id: str
    url: str
    kind: LinkKind
    label: str | None = None
    status: LinkStatus = LinkStatus.NEEDS_REVIEW
    verified_at: date | None = None


class TechnologySummary(BaseModel):
    """Краткая запись для списков/реестра/радара (без links, evidence)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    kind: TechnologyKind
    family: str | None = None
    tier: int | None = None
    groups: list[MeasurementGroup] = Field(default_factory=list)
    is_future: IsFuture = IsFuture.FALSE
    core_idea: str | None = None
    prose_id: str | None = None
    configuration: dict[str, str] = Field(default_factory=dict)
    residual: list[str] = Field(default_factory=list)


class TechnologyFull(TechnologySummary):
    """Полная запись для карточки технологии (включает links)."""

    links: list[Link] = Field(default_factory=list)
    notes: str | None = None
    created_at: Any | None = None
    updated_at: Any | None = None


class EvidenceType(str, Enum):
    PUBLICATION = "publication"
    INDEPENDENT_REPRODUCTION = "independent_reproduction"
    REPOSITORY = "repository"
    BUILD_RUN = "build_run"
    FRAMEWORK_PRESENCE = "framework_presence"
    PACKAGE_DOWNLOADS = "package_downloads"
    INDUSTRIAL_USE = "industrial_use"
    PROVIDER_COUNT = "provider_count"


class Evidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    technology_id: str
    type: EvidenceType
    value: str | None = None
    source: str
    fetched_at: date
    obtained_by: str = "manual"
    verified: bool = False


class MaturityLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"


class MaturityHistoryEntry(BaseModel):
    """Строка журнала версий уровня (обеспечивает 02-AC-2)."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    technology_id: str
    level: MaturityLevel
    confidence: float
    evidence_basis: str = "computed"
    rule_version: str
    computed_at: Any | None = None
    evidence_snapshot: list[int] = Field(default_factory=list)
