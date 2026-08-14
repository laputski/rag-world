"""A RAG configuration as a point in the stratified dimension space.

This is the project's only contract for describing a RAG system: a point in the
space of twenty-eight dimensions grouped into seven strata A–G
(`core/dimensions_schema.py`). Whether a configuration is admissible follows
from the constraints Φ (`requires`, `excludes`, `implies`), not from a list of
exceptions written out in prose.

The configuration identifier (`config_hash`) is stable: the same configuration
always yields the same hash, so registry records and comparison results stay
comparable over time.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from core.dimensions_schema import (
    CONDITIONAL_CODES,
    CORE_CODES,
    DEFAULTS,
    validate,
)


def config_hash(payload: dict[str, str]) -> str:
    """A stable SHA256 over the canonical form of a configuration.

    The `config_hash` field itself is excluded from the payload so that the
    computation is idempotent when applied again to a record that already
    carries one.
    """
    clean = {k: v for k, v in payload.items() if k != "config_hash"}
    blob = str(sorted(clean.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


class Configuration(BaseModel):
    """A RAG configuration in the space of twenty-eight dimensions.

    Conditional dimensions (A6, C4, F1–F3) may be left unset, in which case the
    default from `dimensions_schema.DEFAULTS` applies. The full configuration
    used for hashing includes every dimension with its value filled in.
    """

    model_config = ConfigDict(extra="forbid")

    # The fields are listed explicitly so that Pydantic knows their types; the
    # defaults come from dimensions_schema, the single source of truth about
    # the schema.
    #
    # This list has to be edited by hand whenever the schema changes, and that
    # is deliberate: a new dimension picked up silently would enter the
    # configuration hash while no record had filled it in. The composition
    # check in tests/unit/test_dimensions_schema.py makes forgetting loud.
    A1: str = DEFAULTS["A1"]
    A2: str = DEFAULTS["A2"]
    A3: str = DEFAULTS["A3"]
    A4: str = DEFAULTS["A4"]
    A5: str = DEFAULTS["A5"]
    A6: str = DEFAULTS["A6"]
    A7: str = DEFAULTS["A7"]
    A8: str = DEFAULTS["A8"]
    B1: str = DEFAULTS["B1"]
    B2: str = DEFAULTS["B2"]
    C1: str = DEFAULTS["C1"]
    C2: str = DEFAULTS["C2"]
    C3: str = DEFAULTS["C3"]
    C4: str = DEFAULTS["C4"]
    D1: str = DEFAULTS["D1"]
    D2: str = DEFAULTS["D2"]
    D3: str = DEFAULTS["D3"]
    E1: str = DEFAULTS["E1"]
    E2: str = DEFAULTS["E2"]
    E3: str = DEFAULTS["E3"]
    E4: str = DEFAULTS["E4"]
    E5: str = DEFAULTS["E5"]
    F1: str = DEFAULTS["F1"]
    F2: str = DEFAULTS["F2"]
    F3: str = DEFAULTS["F3"]
    G1: str = DEFAULTS["G1"]
    G2: str = DEFAULTS["G2"]
    G3: str = DEFAULTS["G3"]

    def as_dict(self) -> dict[str, str]:
        """Every dimension in canonical order; this is what hashing reads."""
        return {code: getattr(self, code) for code in CORE_CODES + CONDITIONAL_CODES}

    def config_hash(self) -> str:
        """The stable configuration identifier, sixteen hexadecimal digits."""
        return config_hash(self.as_dict())

    def validate(self) -> list[str]:
        """Errors in the configuration, by value and by Φ; empty means admissible."""
        return validate(self.as_dict())

    def is_valid(self) -> bool:
        return not self.validate()
