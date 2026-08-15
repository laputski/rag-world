"""Tests of the stratified dimension schema and of a configuration.

Covered: the declaration of twenty-eight dimensions, the value catalogues, the
base values, the constraints Φ (every incompatible combination is caught),
`Configuration` with its stable identifier, the degree of independence, and dead
values.
"""

import pytest

from core.configuration import Configuration, config_hash
from core.dimensions_schema import (
    ALL_VALUES,
    BY_CODE,
    CONDITIONAL_CODES,
    CONSTRAINTS,
    CORE_CODES,
    DEFAULTS,
    DIMENSIONS,
    SCHEMA_SIZE,
    STRATA,
    dead_values,
    dimensions_of,
    independence_degree,
    is_valid_value,
    validate,
)

# ─── The declaration of the dimensions ───────────────────────────────────────


def test_schema_size_matches_declaration():
    assert len(DIMENSIONS) == SCHEMA_SIZE == 28
    assert len(CORE_CODES) == 23
    assert len(CONDITIONAL_CODES) == 5


def test_all_strata_a_to_g_present():
    groups = {d.group for d in DIMENSIONS}
    assert groups == {"A", "B", "C", "D", "E", "F", "G"}
    assert set(STRATA) == groups


def test_every_stratum_is_named_and_non_empty():
    for code, name in STRATA.items():
        assert name, f"the stratum {code} has no name"
        assert dimensions_of(code), f"the stratum {code} has no dimensions"


def test_stratum_sizes():
    sizes = {code: len(dimensions_of(code)) for code in STRATA}
    assert sizes == {"A": 8, "B": 2, "C": 4, "D": 3, "E": 5, "F": 3, "G": 3}


def test_dimension_codes_are_unique_and_well_formed():
    codes = [d.code for d in DIMENSIONS]
    assert len(codes) == len(set(codes)), "duplicate dimension codes"
    for code in codes:
        assert code[0] in "ABCDEFG" and code[1:].isdigit(), f"malformed code {code}"


def test_every_dimension_has_nonempty_values_and_default():
    for d in DIMENSIONS:
        assert len(d.values) >= 2, f"{d.code}: at least two values are needed"
        assert d.default in d.values, f"{d.code}: the base {d.default!r} is not a value"


def test_conditional_dimensions_are_exactly_a6_c4_and_f():
    """The conditional ones: A6, C4 and F1–F3."""
    assert set(CONDITIONAL_CODES) == {"A6", "C4", "F1", "F2", "F3"}


def test_is_valid_value():
    assert is_valid_value("A4", "graph")
    assert not is_valid_value("A4", "nonsense")
    assert not is_valid_value("ZZ", "x")


def test_defaults_match_dimensions():
    for d in DIMENSIONS:
        assert DEFAULTS[d.code] == d.default


# ─── Ограничения Φ ───────────────────────────────────────────────────────────


def test_constraints_are_well_formed():
    valid_kinds = {"requires", "excludes", "implies"}
    for c in CONSTRAINTS:
        assert c.kind in valid_kinds
        assert c.dim_a in BY_CODE and c.dim_b in BY_CODE
        assert c.val_a in ALL_VALUES[c.dim_a]
        assert c.val_b in ALL_VALUES[c.dim_b]
        assert c.reason, "a constraint must carry a reason"


def test_validate_rejects_unknown_dimension():
    assert any("unknown dimension" in e for e in validate({"ZZ": "x"}))


def test_validate_rejects_invalid_value():
    assert any("is not in" in e for e in validate({"A4": "nonsense"}))


def test_validate_accepts_default_configuration():
    assert validate(DEFAULTS) == []


def test_tree_topology_allows_dense_representation():
    """A tree and vectors are compatible: the ban generalised one system.

    The schema forbade the combination on the grounds that "Vectorless uses no
    vectors". It is Vectorless that uses none, not the tree index as such: RAPTOR
    builds its tree by recursively clustering representations and searches by
    them. The property of Vectorless is expressed by A5=none.
    """
    # The provenance of the structure is set together with the topology: "there
    # is no structure" and "the index is flat" are one thing said from two sides.
    cfg = {**DEFAULTS, "A4": "tree", "A5": "dense_single", "A8": "computed",
           "C1": "tree_navigation", "D1": "none"}
    assert validate(cfg) == [], "an admissible combination must not be refused"



def test_phi_cross_encoder_requires_vector_representation():
    cfg = {**DEFAULTS, "A5": "lexical", "D1": "cross_encoder", "C1": "lexical"}
    assert any("D1=cross_encoder excludes A5=lexical" in e for e in validate(cfg))


def test_phi_cross_encoder_excludes_non_vector_models():
    for bad in ("none", "lexical", "symbolic"):
        cfg = {**DEFAULTS, "A5": bad, "D1": "cross_encoder"}
        if bad == "lexical":
            cfg["C1"] = "lexical"
        assert any("cross_encoder" in e for e in validate(cfg)), (
            f"A5={bad} must block cross_encoder"
        )
    for good in ("dense_single", "dense_multi_late_interaction", "vision_language"):
        cfg = {**DEFAULTS, "A5": good, "D1": "cross_encoder"}
        assert not any("cross_encoder" in e for e in validate(cfg)), (
            f"A5={good} must not block cross_encoder"
        )


def test_graph_topology_with_cross_encoder_is_valid():
    """A graph architecture with a cross-encoder is admissible, as in PathRAG."""
    cfg = Configuration(A4="graph", C1="graph_traversal", D1="cross_encoder")
    assert not any("cross_encoder" in e for e in cfg.validate()), cfg.validate()


def test_phi_hypergraph_excludes_path_pruning():
    cfg = {**DEFAULTS, "A4": "hypergraph", "D1": "path_pruning", "C1": "boolean_query"}
    assert any("hypergraph" in e for e in validate(cfg))


def test_graph_topology_allows_a_query_language():
    """A graph need not be walked; it can be asked in a graph query language.

    The constraint "a graph requires traversal" generalised one implementation to
    a whole value and twice forced a value onto a record that its sources do not
    state.
    """
    cfg = {**DEFAULTS, "A4": "graph", "A8": "given", "C1": "boolean_query"}
    assert validate(cfg) == []



def test_phi_decoding_reflection_requires_trained_reader():
    """Reflection during decoding requires a reader trained to emit it."""
    cfg = {**DEFAULTS, "E2": "decoding_reflection", "G3": "frozen"}
    assert any("E2=decoding_reflection requires G3=trained_reader" in e
               for e in validate(cfg))


def test_phi_agentic_excludes_post_generation_check():
    cfg = {**DEFAULTS, "C2": "agentic_open_loop", "E2": "post_gen_check"}
    assert any("C2=agentic_open_loop excludes E2=post_gen_check" in e
               for e in validate(cfg))


def test_phi_multi_hop_requires_graph_topology():
    cfg = {**DEFAULTS, "C2": "multi_hop_fixed", "A4": "flat"}
    assert any("multi_hop" in e for e in validate(cfg))


def test_phi_constraint_count_is_pinned():
    """The count of constraints is pinned: a new Φ has to arrive with a test."""
    assert len(CONSTRAINTS) == 10, (
        f"Φ holds {len(CONSTRAINTS)} constraints; add a test for the new one. "
        "The list: " + ", ".join(
            f"{c.dim_a}={c.val_a} {c.kind} {c.dim_b}={c.val_b}" for c in CONSTRAINTS
        )
    )


# ─── A configuration ─────────────────────────────────────────────────────────


def test_configuration_defaults_match_schema():
    cfg = Configuration()
    for code, val in DEFAULTS.items():
        assert getattr(cfg, code) == val


def test_configuration_covers_every_dimension():
    keys = set(Configuration().as_dict())
    assert keys == {d.code for d in DIMENSIONS}


def test_configuration_hash_is_stable_and_idempotent():
    cfg = Configuration(A4="graph", C1="graph_traversal", C2="multi_hop_fixed")
    assert cfg.config_hash() == cfg.config_hash()
    assert len(cfg.config_hash()) == 16


def test_configuration_hash_changes_with_value():
    assert Configuration().config_hash() != Configuration(
        A4="graph", C1="graph_traversal"
    ).config_hash()


def test_config_hash_ignores_own_field():
    """Applying it again to an already marked record yields the same result."""
    payload = Configuration().as_dict()
    first = config_hash(payload)
    assert config_hash({**payload, "config_hash": first}) == first


def test_configuration_validate_uses_phi():
    """The example comes from a live constraint rather than an abandoned one.

    A cross-encoder compares representations, so the representation model has to
    exist.
    """
    cfg = Configuration(D1="cross_encoder", A5="none")
    assert cfg.validate() != []
    assert not cfg.is_valid()


def test_configuration_rejects_unknown_field():
    with pytest.raises(Exception):
        Configuration(ZZ="x")


# ─── Properties of the schema ────────────────────────────────────────────────


def test_independence_degree_is_between_zero_and_one():
    deg = independence_degree()
    assert 0.0 < deg <= 1.0, f"the degree of independence {deg} lies outside (0, 1]"
    assert deg < 1.0, "with live constraints the degree cannot be one"


def test_dead_values_returns_valid_pairs():
    for code, value in dead_values():
        assert code in BY_CODE
        assert value in ALL_VALUES[code]


def test_structure_origin_is_tied_to_topology():
    """"There is no structure" and "the index is flat" are one thing.

    The link runs both ways: a flat index can have no provenance, and an absent
    provenance means a flat index. Without the second direction a record could
    assert a graph with no source for its edges.
    """
    assert validate({**DEFAULTS, "A4": "flat", "A8": "computed"}) != []
    assert validate({**DEFAULTS, "A4": "graph", "A8": "none", "C1": "graph_traversal"}) != []
    assert validate({**DEFAULTS, "A4": "flat", "A8": "none"}) == []


def test_loop_between_generation_and_retrieval_needs_repeated_calls():
    """A loop is impossible with a single retrieval call.

    There is no converse constraint: repeated calls also happen without generation
    taking part, as in a fixed multi-hop traversal.
    """
    assert validate({**DEFAULTS, "E5": "mutual_loop", "C2": "single_shot"}) != []
    assert validate({**DEFAULTS, "E5": "mutual_loop", "C2": "iterative_stopping"}) == []
    # A multi-hop traversal requires a graph by a separate constraint, so the
    # example sets the topology and its provenance as well.
    assert validate({**DEFAULTS, "E5": "none", "C2": "multi_hop_fixed",
                     "A4": "graph", "A8": "extracted",
                     "C1": "graph_traversal"}) == []
