"""The core of RAG World: a formal description of RAG technologies.

The package holds only domain-neutral means of description and assessment:

* `dimensions_schema` — the schema of twenty-eight dimensions across seven
  strata A–G, with the compatibility constraints Φ;
* `configuration` — a configuration as a point in that space, and its stable
  identifier;
* `maturity` — the deterministic rule that derives a level from L0 to L6 out of
  collected evidence, with no language model involved.

That the core stays domain-neutral is checked by
`tests/unit/test_p1_guardian.py`.
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
