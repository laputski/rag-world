"""The deterministic maturity rule for RAG technologies.

A pure function: it takes evidence and returns a level, a confidence and a
basis. No language model, no store access. Writing the result to the level
journal is the caller's job (`scripts/compute_levels.py`), and only when the
level actually changed.

Two decisions shape the rule, and both came out of review.

**Two roads to L2.** L2 is reached either by the scientific road (a
peer-reviewed venue, or independent reproduction) or by the industrial one
(documented production use). Without the industrial road, Contextual Retrieval
— an industry staple that was never peer-reviewed — would sit at L0 or L1, below
a preprint nobody reproduced. That is a straight inversion of what the scale is
for.

**L5 and L6 are marked as entered by a human.** Their sufficient conditions have
no machine-readable source, so a level resting on them carries
`evidence_basis='manual'` and does not pass itself off as computed.

The scale is ordinal: arithmetic over levels is undefined. It is also monotone:
reaching L_k requires the conditions of every level below it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Version of the rule. Changing the logic means raising this and recomputing
# every record, with both versions of the result kept in the level journal so
# that each change stays explainable.
RULE_VERSION = "1.0.0"

# How long evidence of each type stays current. Evidence behind L5 and L6 lasts
# longer because production use changes more slowly than bibliometrics do.
FRESHNESS_DAYS: dict[str, int] = {
    "publication": 365 * 3,           # a publication does not stop being a fact
    "independent_reproduction": 365 * 3,
    "repository": 180,                # repository activity, judged half-yearly
    "build_run": 90,                  # a build and run, judged quarterly
    "framework_presence": 365,
    "package_downloads": 90,
    "industrial_use": 365 * 2,        # production use is stable
    "provider_count": 365 * 2,
}


@dataclass
class EvidenceIn:
    """One piece of evidence, in the neutral shape the rule reads.

    `type` and `value` carry the meaning: which kind of fact this is, and for a
    publication, which class of venue. See `_venue_class` and the level
    conditions below.
    """

    type: str
    source: str
    value: str | None = None
    fetched_at: date | None = None
    verified: bool = False


@dataclass
class MaturityResult:
    level: str            # 'L0'..'L6'
    confidence: float     # 0..1
    evidence_basis: str   # 'computed' | 'manual'
    satisfied: list[str] = field(default_factory=list)   # levels whose conditions hold
    missing: list[str] = field(default_factory=list)     # conditions not met


# ─── Classifying the venue of a publication (for L1 and the scientific L2) ────

# Peer-reviewed venues. The list is approved separately. The `value` of a
# publication may carry a venue name or the marker peer_reviewed=true.
PEER_REVIEWED_VENUES: frozenset[str] = frozenset(
    v.lower()
    for v in (
        # Machine learning and language conferences
        "NeurIPS", "ICLR", "ICML", "ACL", "EMNLP", "NAACL", "AAAI",
        "CVPR", "ICCV", "ECCV",
        # Journals
        "TACL", "JMLR", "Nature", "Nature Communications", "Science",
        # Databases and systems
        "VLDB", "PVLDB", "SIGMOD",
        # Other peer-reviewed venues
        "ECIR", "CIKM", "WSDM", "KDD",
    )
)


def _venue_class(ev: EvidenceIn) -> str:
    """The class of venue, read out of a publication's `value`.

    Returns one of 'peer_reviewed', 'workshop_preprint', 'blog_talk'. The value
    may hold a venue name, the marker 'peer_reviewed=true/false', or a kind
    such as 'arXiv', 'workshop' or 'blog'.
    """
    val = (ev.value or "").lower()
    if "peer_reviewed=true" in val or "peer_reviewed=true" in val.replace(" ", ""):
        return "peer_reviewed"
    for venue in PEER_REVIEWED_VENUES:
        if venue.lower() in val:
            return "peer_reviewed"
    if any(m in val for m in ("workshop", "arxiv", "preprint", "openreview")):
        return "workshop_preprint"
    return "blog_talk"


# ─── Conditions of each level ─────────────────────────────────────────────────


def _has_publication(evidence: list[EvidenceIn], min_class: str) -> bool:
    """Whether a publication exists at a venue class of at least `min_class`.

    The classes are ordered blog_talk < workshop_preprint < peer_reviewed.
    """
    order = {"blog_talk": 0, "workshop_preprint": 1, "peer_reviewed": 2}
    threshold = order[min_class]
    for ev in evidence:
        if ev.type == "publication":
            if order[_venue_class(ev)] >= threshold:
                return True
    return False


def _has(evidence: list[EvidenceIn], etype: str) -> list[EvidenceIn]:
    return [e for e in evidence if e.type == etype]


def _has_any(evidence: list[EvidenceIn], etype: str) -> bool:
    return any(e.type == etype for e in evidence)


# ─── Freshness ────────────────────────────────────────────────────────────────


def _is_fresh(ev: EvidenceIn, as_of: date) -> bool:
    """Evidence is current while the period set for its type has not run out."""
    if ev.fetched_at is None:
        return False  # with no date collected, currency cannot be judged
    days = FRESHNESS_DAYS.get(ev.type, 365)
    return (as_of - ev.fetched_at) <= timedelta(days=days)


# ─── The rule itself ──────────────────────────────────────────────────────────


def compute_level(
    evidence: list[EvidenceIn],
    *,
    as_of: date | None = None,
) -> MaturityResult:
    """Derive the maturity level from evidence, deterministically.

    Returns the highest level whose conditions all hold, under monotonicity: for
    L_k, the conditions of every level below it hold too. Confidence is the
    share of the required evidence for that level which is present, current and
    verified.

    L5 and L6 carry evidence_basis='manual', because their conditions —
    production use, and the number of independent providers — have no
    machine-readable source.
    """
    as_of = as_of or date.today()
    satisfied: list[str] = ["L0"]  # L0 always holds: the technology is described at all

    # ── L1: a publication, preprint or workshop ──
    l1_ok = _has_publication(evidence, "workshop_preprint")
    if l1_ok:
        satisfied.append("L1")

    # ── L2: review, by either of two roads ──
    #   (a) the scientific road: a peer-reviewed venue, which requires L1 by
    #       monotonicity, since a paper implies a paper exists;
    #   (b) a road that does not pass through L1: independent reproduction, or
    #       documented production use. It exists because some techniques are
    #       used everywhere and reviewed nowhere, and placing them below an
    #       unreproduced preprint would invert the scale.
    peer_reviewed_l2 = _has_publication(evidence, "peer_reviewed")
    independent_l2 = _has_any(evidence, "independent_reproduction")
    industrial_l2 = _has_any(evidence, "industrial_use")
    if peer_reviewed_l2 and "L1" in satisfied:
        satisfied.append("L2")  # the scientific road, with monotonicity
    elif independent_l2 or industrial_l2:
        satisfied.append("L2")  # the other roads: L2 without L1

    # ── L3: a reference implementation ──
    # The authors' own repository, or a successful build and run.
    l3_ok = _has_any(evidence, "repository") or _has_any(evidence, "build_run")
    if l3_ok and "L2" in satisfied:
        satisfied.append("L3")

    # ── L4: independent reproduction ──
    # An implementation not by the authors, presence in a framework, or package
    # downloads.
    l4_ok = (
        _has_any(evidence, "independent_reproduction")
        or _has_any(evidence, "framework_presence")
        or _has_any(evidence, "package_downloads")
    )
    if l4_ok and "L3" in satisfied:
        satisfied.append("L4")

    # ── L5: production use, entered by a human ──
    # Documented use in a production environment.
    l5_ok = _has_any(evidence, "industrial_use")
    if l5_ok and "L4" in satisfied:
        satisfied.append("L5")

    # ── L6: an industry standard, entered by a human ──
    # Implemented independently by three or more providers.
    l6_ok = _has_any(evidence, "provider_count")
    if l6_ok and "L5" in satisfied:
        satisfied.append("L6")

    level = satisfied[-1]
    basis = "manual" if level in ("L5", "L6") else "computed"
    confidence = _confidence_for(level, evidence, as_of)
    missing = [lv for lv in ("L1", "L2", "L3", "L4", "L5", "L6") if lv not in satisfied]
    return MaturityResult(
        level=level,
        confidence=confidence,
        evidence_basis=basis,
        satisfied=satisfied,
        missing=missing,
    )


def _confidence_for(level: str, evidence: list[EvidenceIn], as_of: date) -> float:
    """The share of the required evidence for a level that is current and verified.

    L0 has no requirements, so its confidence is 1.0 by definition. For L1 to L6
    it is the share of the evidence types required by that level which are
    present, current and verified.
    """
    if level == "L0":
        return 1.0

    required: list[str]
    if level == "L1":
        required = ["publication"]
    elif level == "L2":
        # The scientific road to L2 wants a peer-reviewed publication or an
        # independent reproduction; the industrial one wants production use.
        # For confidence all three count as alternatives, and whichever were
        # reached are the ones measured.
        required = ["publication", "independent_reproduction", "industrial_use"]
    elif level == "L3":
        required = ["repository", "build_run"]
    elif level == "L4":
        required = ["independent_reproduction", "framework_presence", "package_downloads"]
    elif level == "L5":
        required = ["industrial_use"]
    else:  # L6
        required = ["provider_count"]

    # Where a level admits alternatives, confidence is measured over the
    # alternatives actually reached, by how much of their evidence is current
    # and verified.
    present_types = {e.type for e in evidence}
    met = [t for t in required if t in present_types]
    if not met:
        return 0.0
    # Confidence is the mean, over the alternatives reached, of the share of
    # that type which is current and verified.
    per_alt: list[float] = []
    for t in met:
        of_type = [e for e in evidence if e.type == t]
        if not of_type:
            continue
        good = sum(1 for e in of_type if _is_fresh(e, as_of) and e.verified)
        per_alt.append(good / len(of_type))
    return round(sum(per_alt) / len(per_alt), 3) if per_alt else 0.0
