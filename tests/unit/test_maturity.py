"""Tests for the deterministic maturity level function (STAGE-6 Ф2, plan 02 §3).

Покрывает: монотонность, двойной путь к L2 (02-1), manual basis для L5/L6 (02-3),
детерминизм, уверенность (определение 5), свежесть свидетельств.
"""

from datetime import date, timedelta

from core.maturity import RULE_VERSION, EvidenceIn, compute_level

TODAY = date(2026, 8, 5)
FRESH = TODAY - timedelta(days=30)
STALE_PUB = TODAY - timedelta(days=365 * 5)  # публикация: свежесть 3 года → устарела


def _pub(venue: str, fetched: date = FRESH, verified: bool = True) -> EvidenceIn:
    return EvidenceIn(
        type="publication", source="x", value=venue,
        fetched_at=fetched, verified=verified,
    )


def _ev(etype: str, source: str = "x", **kw) -> EvidenceIn:
    """Свежее проверенное свидетельство произвольного типа (default)."""
    kw.setdefault("fetched_at", FRESH)
    kw.setdefault("verified", True)
    return EvidenceIn(type=etype, source=source, **kw)


# ─── монотонность и базовые уровни ────────────────────────────────────────────


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
    # Репозиторий без публикации не даёт L3 (нет L1/L2).
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


# ─── 02-1: двойной путь к L2 (Contextual Retrieval) ─────────────────────────


def test_industrial_use_reaches_l2_without_publication():
    """Решение 02-1: отраслевой путь к L2 без рецензирования.

    Contextual Retrieval опубликован как отраслевая заметка без рецензирования,
    но применяется повсеместно. По научному пути он получил бы L0/L1 и оказался
    ниже препринта — инверсия. Отраслевой путь поднимает его до L2.
    """
    r = compute_level(
        [_ev("industrial_use", "anthropic.com")],
        as_of=TODAY,
    )
    assert r.level == "L2"
    assert r.satisfied == ["L0", "L2"]  # L1 пропущен (отраслевой путь)


def test_contextual_retrieval_scenario():
    """Конкретный сценарий Contextual Retrieval: блог + industrial_use."""
    ev = [
        _pub("Anthropic blog (no peer review)"),  # blog_talk → L0 по научному
        _ev("industrial_use", "anthropic.com/news/contextual-retrieval"),
    ]
    r = compute_level(ev, as_of=TODAY)
    assert r.level == "L2"  # отраслевой путь


def test_independent_reproduction_reaches_l2():
    """Независимое воспроизведение — тоже путь к L2 (без peer review)."""
    r = compute_level(
        [_ev("independent_reproduction", "third-party-paper")],
        as_of=TODAY,
    )
    assert r.level == "L2"


# ─── 02-3: manual basis для L5/L6 ─────────────────────────────────────────────


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
        assert r.evidence_basis == "computed", f"{r.level} должно быть computed"


# ─── детерминизм ─────────────────────────────────────────────────────────────


def test_deterministic_same_input_same_output():
    ev = [_pub("ICLR 2024"), _ev("repository", "gh")]
    a = compute_level(ev, as_of=TODAY)
    b = compute_level(ev, as_of=TODAY)
    assert (a.level, a.confidence, a.evidence_basis) == (b.level, b.confidence, b.evidence_basis)


# ─── уверенность и свежесть (определение 5) ──────────────────────────────────


def test_stale_evidence_lowers_confidence():
    """Свидетельство старше периода актуальности не засчитывается в уверенность."""
    fresh = compute_level([_pub("ICLR 2024", fetched=FRESH)], as_of=TODAY)
    stale = compute_level([_pub("ICLR 2024", fetched=STALE_PUB)], as_of=TODAY)
    assert fresh.confidence > stale.confidence
    assert stale.confidence == 0.0  # публикация 5 лет → устарела (срок 3 года)


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


# ─── версия правила ──────────────────────────────────────────────────────────


def test_rule_version_is_present_and_semver():
    parts = RULE_VERSION.split(".")
    assert len(parts) == 3, "RULE_VERSION должна быть в формате semver M.m.p"
    assert all(p.isdigit() for p in parts)
