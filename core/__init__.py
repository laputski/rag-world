"""Ядро RAG World: формальное описание технологий RAG.

Пакет содержит только предметно-нейтральные средства описания и оценки:

* `dimensions_schema` — схема из двадцати восьми измерений в семи стратах A–G
  с ограничениями совместимости Φ;
* `configuration` — конфигурация как точка этого пространства и её устойчивый
  идентификатор;
* `maturity` — детерминированное правило уровня зрелости L0–L6 по собранным
  свидетельствам, без языковой модели.

Предметная нейтральность ядра проверяется `tests/unit/test_p1_guardian.py`.
"""

from core.configuration import Configuration, config_hash
from core.dimensions_schema import (
    CONDITIONAL_CODES,
    CONSTRAINTS,
    CORE_CODES,
    DEFAULTS,
    DIMENSIONS,
    Constraint,
    Dimension,
    dead_values,
    independence_degree,
    is_valid_value,
    validate,
)
from core.maturity import RULE_VERSION, EvidenceIn, compute_level

__all__ = [
    "CONDITIONAL_CODES",
    "CONSTRAINTS",
    "CORE_CODES",
    "DEFAULTS",
    "DIMENSIONS",
    "Configuration",
    "Constraint",
    "Dimension",
    "EvidenceIn",
    "RULE_VERSION",
    "compute_level",
    "config_hash",
    "dead_values",
    "independence_degree",
    "is_valid_value",
    "validate",
]
