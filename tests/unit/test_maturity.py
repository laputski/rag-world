"""Tests of the deterministic maturity-level function.

Covered: monotonicity, the two routes to L2, the manual basis required for L5 and
L6, determinism, confidence, and the freshness of evidence.
"""

from datetime import date, timedelta

from core.maturity import (
    FRESHNESS_DAYS,
    LEVEL_RULES,
    RULE_VERSION,
    EvidenceIn,
    LevelRule,
    Road,
    compute_level,
)

TODAY = date(2026, 8, 5)
FRESH = TODAY - timedelta(days=30)
STALE_PUB = TODAY - timedelta(days=365 * 5)  # a publication is fresh for 3 years


def _pub(venue: str, fetched: date = FRESH, verified: bool = True) -> EvidenceIn:
    return EvidenceIn(
        type="publication", source="x", value=venue,
        fetched_at=fetched, verified=verified,
    )


def _ev(etype: str, source: str = "x", **kw) -> EvidenceIn:
    """A fresh verified piece of evidence of an arbitrary type."""
    kw.setdefault("fetched_at", FRESH)
    kw.setdefault("verified", True)
    return EvidenceIn(type=etype, source=source, **kw)


# ─── Monotonicity and the base levels ────────────────────────────────────────


def test_empty_evidence_gives_l0():
    r = compute_level([], as_of=TODAY)
    assert r.level == "L0"
    assert r.satisfied == ["L0"]
    assert r.confidence == 1.0


def test_blog_only_stays_l0():
    r = compute_level([_pub("Some blog post")], as_of=TODAY)
    assert r.level == "L0"
    assert "L1" in r.missing


def test_preprint_reaches_l1_not_l2():
    r = compute_level([_pub("arXiv preprint")], as_of=TODAY)
    assert r.level == "L1"
    assert "L2" in r.missing


def test_peer_reviewed_reaches_l2():
    r = compute_level([_pub("NeurIPS 2024")], as_of=TODAY)
    assert r.level == "L2"
    assert r.satisfied == ["L0", "L1", "L2"]


def test_monotonicity_l3_requires_l2():
    # A repository without a publication does not give L3: L1 and L2 are missing.
    r = compute_level(
        [_ev("repository", "gh")],
        as_of=TODAY,
    )
    assert r.level == "L0"


def test_full_progression_to_l4():
    r = compute_level(
        [
            _pub("ICLR 2024"),
            _ev("repository", "gh"),
            _ev("framework_presence", "langchain"),
        ],
        as_of=TODAY,
    )
    assert r.level == "L4"
    assert r.satisfied == ["L0", "L1", "L2", "L3", "L4"]


# ─── The two routes to L2 ────────────────────────────────────────────────────


def test_industrial_use_reaches_l2_without_publication():
    """The industrial route to L2, with no peer review.

    Contextual Retrieval was published as an industry note without review and is
    applied everywhere. By the scholarly route it would rank below a preprint,
    which inverts the meaning. The industrial route raises it to where it belongs.
    """
    r = compute_level(
        [_ev("industrial_use", "anthropic.com")],
        as_of=TODAY,
    )
    assert r.level == "L2"
    assert r.satisfied == ["L0", "L2"]  # L1 is bypassed on the industrial route


def test_contextual_retrieval_scenario():
    """The concrete Contextual Retrieval case: an industry note plus industrial use."""
    ev = [
        _pub("Anthropic blog (no peer review)"),  # L0 by the scholarly route
        _ev("industrial_use", "anthropic.com/news/contextual-retrieval"),
    ]
    r = compute_level(ev, as_of=TODAY)
    assert r.level == "L2"  # the industrial route


def test_independent_reproduction_reaches_l2():
    """An independent reproduction is also a route to L2, with no peer review."""
    r = compute_level(
        [_ev("independent_reproduction", "third-party-paper")],
        as_of=TODAY,
    )
    assert r.level == "L2"


# ─── A manual basis is required for L5 and L6 ────────────────────────────────


def test_l5_marked_manual_basis():
    r = compute_level(
        [
            _pub("NeurIPS 2024"),
            _ev("repository", "gh"),
            _ev("framework_presence", "langchain"),
            _ev("industrial_use", "vendor-docs"),
        ],
        as_of=TODAY,
    )
    assert r.level == "L5"
    assert r.evidence_basis == "manual"


def test_l6_marked_manual_basis():
    r = compute_level(
        [
            _pub("NeurIPS 2024"),
            _ev("repository", "gh"),
            _ev("framework_presence", "langchain"),
            _ev("industrial_use", "vendor"),
            _ev("provider_count", "3 vendors"),
        ],
        as_of=TODAY,
    )
    assert r.level == "L6"
    assert r.evidence_basis == "manual"


def test_l0_to_l4_is_computed_basis():
    for evidence in [
        [_pub("arXiv")],
        [_pub("ICLR")],
        [_pub("ICLR"), _ev("repository", "gh")],
    ]:
        r = compute_level(evidence, as_of=TODAY)
        assert r.evidence_basis == "computed", f"{r.level} has to be computed"


# ─── Determinism ─────────────────────────────────────────────────────────────


def test_deterministic_same_input_same_output():
    ev = [_pub("ICLR 2024"), _ev("repository", "gh")]
    a = compute_level(ev, as_of=TODAY)
    b = compute_level(ev, as_of=TODAY)
    assert (a.level, a.confidence, a.evidence_basis) == (b.level, b.confidence, b.evidence_basis)


# ─── Confidence and freshness ────────────────────────────────────────────────


def test_stale_evidence_lowers_confidence():
    """Evidence older than its period of relevance does not count."""
    fresh = compute_level([_pub("ICLR 2024", fetched=FRESH)], as_of=TODAY)
    stale = compute_level([_pub("ICLR 2024", fetched=STALE_PUB)], as_of=TODAY)
    assert fresh.confidence > stale.confidence
    assert stale.confidence == 0.0  # five years old against a three-year window


def test_unverified_evidence_lowers_confidence():
    verified = compute_level([_pub("ICLR 2024", verified=True)], as_of=TODAY)
    unverified = compute_level([_pub("ICLR 2024", verified=False)], as_of=TODAY)
    assert verified.confidence > unverified.confidence


def test_confidence_between_zero_and_one():
    for ev in [
        [_pub("arXiv", verified=False)],
        [_pub("NeurIPS"), _ev("repository", "gh")],
    ]:
        r = compute_level(ev, as_of=TODAY)
        assert 0.0 <= r.confidence <= 1.0


# ─── The version of the rule ─────────────────────────────────────────────────


def test_rule_version_is_present_and_semver():
    parts = RULE_VERSION.split(".")
    assert len(parts) == 3, "RULE_VERSION has to be semver, M.m.p"
    assert all(p.isdigit() for p in parts)


# ─── The displayed rule against the executed one ─────────────────────────────


def _evidence_for(level: str, road: Road) -> list[EvidenceIn]:
    """Evidence that takes a technology to `level` by `road`, and no further.

    The prerequisite levels are walked down through the first road of each, that
    being the shortest way: only what the roads themselves name gets in, so the
    result cannot accidentally satisfy a level the table did not ask for.
    """
    items: list[EvidenceIn] = []
    if road.requires:
        below = _rule_for(road.requires)
        items += _evidence_for(below.level, below.roads[0])
    if road.evidence == "publication":
        items.append(_pub("NeurIPS" if road.venue == "peer_reviewed" else "arXiv preprint"))
    else:
        items.append(_ev(road.evidence))
    return items


def _rule_for(level: str) -> LevelRule:
    return next(r for r in LEVEL_RULES if r.level == level)


def test_rule_table_agrees_with_the_rule():
    """Every road in the displayed table has to lead where the table says.

    The table is a second description of the conditions, kept because the rule
    has to be shown to a reader and not only run. A second description of one
    thing is the defect this project was built to remove, so it is checked
    rather than trusted: evidence is assembled out of each road and put through
    the rule itself.
    """
    for rule in LEVEL_RULES:
        if not rule.roads:  # L0 asks for nothing and is reached with no evidence
            assert compute_level([], as_of=TODAY).level == rule.level
            continue
        for road in rule.roads:
            result = compute_level(_evidence_for(rule.level, road), as_of=TODAY)
            assert result.level == rule.level, (
                f"the table promises {rule.level} by {road.evidence}, "
                f"the rule answers {result.level}"
            )
            assert result.evidence_basis == rule.basis


def test_every_level_of_the_scale_is_in_the_table():
    """A level left out of the table disappears from the article and the map hint."""
    assert [r.level for r in LEVEL_RULES] == ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]


def test_the_table_names_only_evidence_the_freshness_periods_cover():
    """Evidence with no period of relevance would never count as current."""
    named = {road.evidence for rule in LEVEL_RULES for road in rule.roads}
    assert named <= set(FRESHNESS_DAYS), (
        f"no freshness period declared for {sorted(named - set(FRESHNESS_DAYS))}"
    )
