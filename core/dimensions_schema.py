"""The stratified configuration space: 28 dimensions and the constraints Φ.

A declarative statement of the schema the whole project rests on: any RAG system
is represented as a point in this space. The dimensions are grouped into seven
strata A–G — knowledge representation, query formulation, retrieval, context
assembly, synthesis and control, state evolution, constraint envelope.

The module is domain-neutral: the structure of the space and nothing else, no
adapters and no backends. Values are stable ASCII codes, and the labels a person
reads live in the interface localisation.

Each dimension carries a code (A1..G3), a name, an ordered list of values, a
mark of whether it is core or conditional, and for a conditional one the guard
under which it is defined. Constraints Φ come in three kinds:

  requires — a value requires another value;
  excludes — a value rules another one out;
  implies  — a value entails another dimension's value by default.

The coupling between decisions is stated by these constraints explicitly:
inadmissible combinations are found by validate(), not by a list of exceptions
written out in prose.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    code: str            # A1..G3
    name: str            # human-readable name
    values: tuple[str, ...]
    core: bool = True    # core dimensions are always defined; the rest are conditional
    guard: str = ""      # the condition under which a conditional dimension is defined
    # The base value: it applies when the dimension is not set explicitly.
    default: str = ""

    @property
    def group(self) -> str:
        return self.code[0]


@dataclass(frozen=True)
class Constraint:
    """A constraint Φ between values of two dimensions.

    kind:
      'requires' — (dim_a, val_a) requires (dim_b, val_b) to be present. If
                   (dim_a, val_a) is there while dim_b is absent or differs,
                   that is an error.
      'excludes' — (dim_a, val_a) and (dim_b, val_b) cannot occur together.
      'implies'  — the same as requires, applied as a default when completing a
                   partial configuration.
    """

    kind: str
    dim_a: str
    val_a: str
    dim_b: str
    val_b: str
    reason: str = ""


# ─── The dimensions ───────────────────────────────────────────────────────────

DIMENSIONS: tuple[Dimension, ...] = (
    # Stratum A — Knowledge representation
    Dimension("A1", "Unit of retrieval",
              ("passage", "proposition", "entity", "node_edge",
               "page_image", "table_row", "summary_node"), default="passage"),
    Dimension("A2", "Segmentation",
              ("fixed", "structure_aware", "late_chunking", "semantic", "none"),
              default="fixed"),
    Dimension("A3", "Unit enrichment",
              ("none", "context_prefix", "summary", "extracted_triples", "metadata"),
              default="none"),
    Dimension("A4", "Index topology",
              ("flat", "tree", "graph", "hypergraph", "community_hierarchy"),
              default="flat"),
    Dimension("A5", "Representation model",
              ("lexical", "dense_single", "dense_multi_late_interaction",
               "symbolic", "vision_language", "none"),
              default="dense_single"),
    Dimension("A6", "Temporality",
              ("snapshot", "append_only", "bitemporal"),
              core=False, guard="defined when F1 is not none, that is, when state evolves",
              default="snapshot"),
    Dimension("A7", "Modality",
              ("text", "image", "table", "audio", "scene_3d"), default="text"),
    # Topology says what kind of structure sits over the data, not where that
    # structure came from. The difference is not a nuance: a document's table of
    # contents is correct by construction, whereas a hierarchy computed by
    # clustering may turn out poor and changes on reindexing. Vectorless and
    # RAPTOR both have a tree, and without this dimension they are
    # indistinguishable.
    Dimension("A8", "Origin of index structure",
              ("none", "given", "extracted", "computed"), default="none"),

    # Stratum B — Query formulation
    Dimension("B1", "Query transformation",
              ("identity", "hyde", "multi_reformulation", "step_back",
               "subquestion_decomposition"), default="identity"),
    Dimension("B2", "Routing",
              ("static", "trained_classifier", "llm_router", "cost_aware_policy"),
              default="static"),

    # Stratum C — Retrieval
    Dimension("C1", "Search operator",
              ("ann", "lexical", "graph_traversal", "boolean_query",
               "tree_navigation", "spatial_range"), default="ann"),
    Dimension("C2", "Traversal control",
              ("single_shot", "multi_hop_fixed", "iterative_stopping",
               "agentic_open_loop"), default="single_shot"),
    Dimension("C3", "Source fusion",
              ("none", "rrf", "score_normalization", "learned_fusion"),
              default="none"),
    Dimension("C4", "Distribution",
              ("single_store", "multiple_local", "federation"),
              core=False, guard="defined when more than one store is involved",
              default="single_store"),

    # Stratum D — Context assembly
    #
    # The base value of D1 used to be `cross_encoder`, and that inverted the
    # meaning of the reference point: reranking is a technique, and the base
    # configuration describes its absence. Thirty-four records that rerank
    # nothing were shown as departing from the base, while twenty-five using a
    # joint encoder were shown as matching it. Naive Dense, whose prose calls
    # itself the reference point, differed from it in exactly this dimension.
    #
    # A hidden inconsistency went with it: a constraint Φ forbids
    # `cross_encoder` with a lexical, symbolic or absent representation model,
    # so a record with such a model and no explicit D1 was completed into an
    # inadmissible configuration.
    Dimension("D1", "Reranking",
              ("none", "cross_encoder", "graph_structural", "set_cover",
               "path_pruning"), default="none"),
    Dimension("D2", "Selection and compression",
              ("top_k", "budget_aware", "abstractive_compression",
               "latent_compression"), default="top_k"),
    Dimension("D3", "Arrangement",
              ("natural_order", "reliability_ascending", "hierarchical"),
              default="natural_order"),

    # Stratum E — Synthesis and control
    Dimension("E1", "Generation mode",
              ("single_pass", "draft_verify", "ensemble_fragments",
               "multi_agent"), default="single_pass"),
    Dimension("E2", "Groundedness control",
              ("none", "pre_gen_grounding", "post_gen_check",
               "decoding_reflection", "decoding_trigger", "external_judge"),
              default="none"),
    Dimension("E3", "Attribution",
              ("none", "document_level", "fragment_level", "claim_level"),
              default="none"),
    # Traversal control (C2) says how many times the system goes to retrieval;
    # the generation mode (E1) says how synthesis is arranged. The link between
    # the two is expressed by neither. HyDE composes a query once, and what is
    # found no longer affects what was composed; IRCoT runs a loop where the
    # reasoning sets the query and what is found changes the reasoning. In the
    # schema they used to differ only by the number of retrieval calls.
    Dimension("E5", "Coupling of generation to retrieval",
              ("none", "generation_seeds", "mutual_loop"), default="none"),
    Dimension("E4", "Refusal policy",
              ("no_refusal", "confidence_threshold", "domain_policy"),
              default="no_refusal"),

    # Stratum F — State evolution
    Dimension("F1", "Write-back",
              ("none", "episodic", "consolidating"),
              core=False, guard="defined for systems that keep memory", default="none"),
    Dimension("F2", "Conflict resolution",
              ("none", "by_time", "by_authority", "explicit_reconciliation"),
              core=False, guard="defined when F1 is not none", default="none"),
    Dimension("F3", "Forgetting",
              ("none", "by_ttl", "by_significance_decay"),
              core=False, guard="defined when F1 is not none", default="none"),

    # Stratum G — Constraint envelope
    Dimension("G1", "Privacy",
              ("open", "isolated_circuit", "differential_privacy", "tee"),
              default="open"),
    Dimension("G2", "Execution site",
              ("server", "edge_device", "mixed"), default="server"),
    Dimension("G3", "Trainability of components",
              ("frozen", "trained_retriever", "trained_reader", "joint_training"),
              default="frozen"),
)

# The composition of the schema: A1–A8 = 8, B1–B2 = 2, C1–C4 = 4, D1–D3 = 3,
# E1–E5 = 5, F1–F3 = 3, G1–G3 = 3, twenty-eight dimensions in all, five of them
# conditional: A6, C4, F1–F3. The count is fixed by a check so that changing the
# composition is a deliberate act: an edit to the schema requires the scientific
# text and the registry data to be updated in the same breath.
#
# Two dimensions entered through the residual queue: the provenance of the index
# structure (A8) and the coupling of generation to retrieval (E5). Neither was
# proposed by a hunch; both were proposed by a count. The first had to be
# written into the residual of four records, the second of six.
SCHEMA_SIZE = 28
_n = len(DIMENSIONS)
assert _n == SCHEMA_SIZE, f"expected {SCHEMA_SIZE} dimensions, defined {_n}"

# Lookup by code.
BY_CODE: dict[str, Dimension] = {d.code: d for d in DIMENSIONS}
CORE_CODES: tuple[str, ...] = tuple(d.code for d in DIMENSIONS if d.core)
CONDITIONAL_CODES: tuple[str, ...] = tuple(d.code for d in DIMENSIONS if not d.core)
ALL_VALUES: dict[str, tuple[str, ...]] = {d.code: d.values for d in DIMENSIONS}
DEFAULTS: dict[str, str] = {d.code: d.default for d in DIMENSIONS}


# ─── Constraints Φ ───────────────────────────────────────────────────────────
# Every incompatible or requiring combination of values is stated here
# explicitly and checked automatically. The list grows as architectures appear
# that expose a new incompatibility.

CONSTRAINTS: tuple[Constraint, ...] = (
    # A flat index and the absence of structure are one thing said from two
    # sides. The link runs both ways, so it is written in both directions.
    Constraint("requires", "A4", "flat", "A8", "none",
               reason="a flat index has no structure, hence no provenance for one"),
    Constraint("requires", "A8", "none", "A4", "flat",
               reason="the absence of structure means a flat index"),
    # A loop between generation and retrieval is impossible without repeated
    # retrieval calls. There is no converse constraint: repeated calls also
    # happen without generation taking part, as in a fixed multi-hop traversal.
    Constraint("excludes", "E5", "mutual_loop", "C2", "single_shot",
               reason="a generation-retrieval loop requires repeated retrieval calls"),

    # Constraints saying "a tree excludes vectors" stood here and were removed:
    # they generalised a property of one system to a whole value. It is
    # Vectorless that uses no vectors, not the tree index as such — RAPTOR
    # builds its tree by recursively clustering representations and searches by
    # those same representations. The property belongs to Vectorless alone, it
    # is expressed by A5=none, and it needs no separate prohibition.
    #
    # The lesson generalises: an incompatibility belongs here only when it
    # follows from what the values are, not from the first system encountered
    # happening to lack the combination.
    #
    # A cross-encoder is incompatible with non-vector representation models
    # (none, lexical, symbolic) and admissible with all vector ones, because it
    # works over any vector input. That admits a graph store together with a
    # cross-encoder, as in PathRAG, where reranking is applied over results
    # obtained from the graph.
    Constraint("excludes", "D1", "cross_encoder", "A5", "none",
               reason="a cross-encoder requires vector input, and none is not one"),
    Constraint("excludes", "D1", "cross_encoder", "A5", "lexical",
               reason="a cross-encoder requires vector input, and lexical is not one"),
    Constraint("excludes", "D1", "cross_encoder", "A5", "symbolic",
               reason="a cross-encoder requires vector input, and symbolic is not one"),
    # A hypergraph ontology selects context by covering sets of hyperedges, so
    # there are no paths in it to prune.
    Constraint("excludes", "A4", "hypergraph", "D1", "path_pruning",
               reason="a hypergraph ontology covers sets, it does not prune paths"),
    # A constraint saying "a graph requires traversal" stood here and was
    # removed for the same reason: it too generalised one implementation to a
    # whole value. A graph need not be walked step by step; it can be asked in
    # the query language of a graph database, which is how Unified RAG works and
    # is ordinary practice rather than an exception. For the second time running,
    # a constraint was forcing a value onto a record that its sources do not
    # state.
    #
    # Reflection during decoding is performed by special tokens the reader emits,
    # and a frozen reader emits none of them.
    Constraint("requires", "E2", "decoding_reflection", "G3", "trained_reader",
               reason="reflection during decoding requires a reader trained to emit it"),
    # An open agentic loop already decides whether what was found suffices, so a
    # separate check after generation duplicates that decision.
    Constraint("excludes", "C2", "agentic_open_loop", "E2", "post_gen_check",
               reason="an open agentic loop already checks what was found"),
    # A hop leads from one node to another, so a fixed multi-hop traversal is
    # meaningful only over a graph.
    Constraint("requires", "C2", "multi_hop_fixed", "A4", "graph",
               reason="multi-hop traversal is meaningful only over a graph"),
)


# ─── The configuration-checking interface ─────────────────────────────────────


def is_valid_value(code: str, value: str) -> bool:
    return value in ALL_VALUES.get(code, ())


def validate(config: dict[str, str]) -> list[str]:
    """Return the configuration's errors; an empty list means it is admissible.

    Two things are checked: that every value belongs to its dimension, and that
    no requires or excludes constraint is broken. A conditional dimension may be
    absent, meaning its guard does not hold, and that is not an error.
    """
    errors: list[str] = []

    # Values belong to their dimensions.
    for code, value in config.items():
        if code not in BY_CODE:
            errors.append(f"unknown dimension {code!r}")
            continue
        if not is_valid_value(code, value):
            errors.append(
                f"dimension {code}: {value!r} is not in {ALL_VALUES[code]}"
            )

    # Constraints Φ hold.
    for c in CONSTRAINTS:
        a_val = config.get(c.dim_a)
        b_val = config.get(c.dim_b)
        if a_val != c.val_a:
            continue  # the constraint is dormant: its left-hand value is absent
        if c.kind == "excludes":
            if b_val == c.val_b:
                errors.append(
                    f"{c.dim_a}={c.val_a} excludes {c.dim_b}={c.val_b}: {c.reason}"
                )
        elif c.kind == "requires":
            # If the required dimension is set, it must match. If it is absent,
            # that is no error for a conditional dimension, and for a core one it
            # is caught by the completeness check elsewhere. Only a conflict is
            # reported here.
            if b_val is not None and b_val != c.val_b:
                errors.append(
                    f"{c.dim_a}={c.val_a} requires {c.dim_b}={c.val_b}, "
                    f"got {c.dim_b}={b_val!r}: {c.reason}"
                )
    return errors


def independence_degree() -> float:
    """Approximate the degree to which the schema's decisions are independent.

    Computing the quantity exactly would mean enumerating some 10^14
    configurations, which cannot be done. A local approximation is used instead:
    the share of value pairs drawn from two different core dimensions that no
    excludes constraint forbids, among all such pairs.

    The number is descriptive, and it must not be read as a measure of
    improvement between versions of the schema. Splitting one dimension into two
    raises it while nothing about the subject matter has changed.
    """
    # Every pair of values drawn from two different core dimensions.
    excludes_pairs: set[tuple[str, str, str, str]] = {
        (c.dim_a, c.val_a, c.dim_b, c.val_b) for c in CONSTRAINTS if c.kind == "excludes"
    }
    core_dims = [d for d in DIMENSIONS if d.core]
    total_pairs = 0
    forbidden_pairs = 0
    for i, di in enumerate(core_dims):
        for dj in core_dims[i + 1:]:
            for vi in di.values:
                for vj in dj.values:
                    total_pairs += 1
                    if (di.code, vi, dj.code, vj) in excludes_pairs or (
                        dj.code, vj, di.code, vi
                    ) in excludes_pairs:
                        forbidden_pairs += 1
    if total_pairs == 0:
        return 1.0
    return round(1.0 - forbidden_pairs / total_pairs, 4)


def dead_values() -> list[tuple[str, str]]:
    """Dead values: those unreachable in any admissible configuration.

    Full enumeration is again out of reach, so the analysis is local. A value
    counts as dead when it stands in an excludes constraint that forbids it
    together with every value of some other dimension, or in a requires
    constraint demanding a value the catalogue does not contain.

    This is a lower bound. Subtler forms of deadness exist, but finding them
    requires solving the constraint system.
    """
    dead: list[tuple[str, str]] = []
    for d in DIMENSIONS:
        if not d.core:
            continue
        for v in d.values:
            if _is_locally_dead(d.code, v):
                dead.append((d.code, v))
    return dead


def _is_locally_dead(code: str, value: str) -> bool:
    """Check a single value for local deadness against excludes and requires."""
    # Requires a value absent from the catalogue, hence unreachable.
    for c in CONSTRAINTS:
        if c.kind == "requires" and c.dim_a == code and c.val_a == value:
            if c.val_b not in ALL_VALUES.get(c.dim_b, ()):
                return True
        # Excluded together with every value of another dimension.
        if c.kind == "excludes" and c.dim_a == code and c.val_a == value:
            other = BY_CODE.get(c.dim_b)
            if other and len(other.values) == 1 and c.val_b == other.values[0]:
                return True
    return False


# ─── Strata ──────────────────────────────────────────────────────────────────

STRATA: dict[str, str] = {
    "A": "Knowledge representation",
    "B": "Query formulation",
    "C": "Retrieval",
    "D": "Context assembly",
    "E": "Synthesis and control",
    "F": "State evolution",
    "G": "Constraint envelope",
}


def dimensions_of(stratum: str) -> tuple[Dimension, ...]:
    """The dimensions of one stratum, in the order they are declared."""
    return tuple(d for d in DIMENSIONS if d.group == stratum)
