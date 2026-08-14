"""The cross-check stage: deterministic checks over candidate evidence.

The stage holds candidate evidence to the same discipline of groundedness the
portal demands of its own claims: every assertion must be supported by what the
source literally says. No language model takes part, and every check here is
deterministic.

What is checked:

  1. The title matches. The title the source returned is compared with the
     title the registry expects. This is the check that found three links whose
     identifier resolved while the work behind it was a different one.
  2. The year of publication is plausible.
  3. Numeric values fall in an admissible range: no negative citation counts and
     no downloads below zero.
  4. The host of the source is on the allowlist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.collectors.base import RawEvidence, is_allowed_host


@dataclass
class CheckResult:
    """The outcome of checking one piece of evidence."""

    passed: bool
    reasons: list[str] = field(default_factory=list)


def _normalize_title(s: str) -> str:
    """Normalise a title for comparison: lower case, punctuation removed."""
    s = s.lower()
    # Everything that is not a letter or a digit becomes a space.
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def _title_similarity(a: str, b: str) -> float:
    """A coarse similarity of two titles: the share of words they share."""
    wa = set(_normalize_title(a).split())
    wb = set(_normalize_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


#: Quantities that are never negative, and how a collector writes them into the
#: value. The list follows what the collectors actually write: a pattern that
#: does not match the format is a protection that does not exist.
_NON_NEGATIVE: tuple[tuple[str, str], ...] = (
    (r"cited_by=(-?\d+)", "the citation count is negative"),
    (r"citation_velocity=(-?[\d.]+)", "the citation velocity is negative"),
    (r"downloads_last_month=(-?\d+)", "the download count is negative"),
    (r"stars=(-?\d+)", "the number of stars is negative"),
)

#: The lower bound on a year of publication: no work predates computing.
MIN_YEAR = 1900

# Below this similarity the titles count as different and the evidence is
# rejected. The threshold is moderate on purpose: it catches an outright
# mismatch between two unrelated works while admitting a title given in short
# and in full form.
TITLE_SIMILARITY_THRESHOLD = 0.6


def check(evidence: RawEvidence) -> CheckResult:
    """Check one piece of evidence deterministically.

    When the result does not pass, the evidence is not written to the registry.
    """
    reasons: list[str] = []

    # The host of the source is on the allowlist.
    if not is_allowed_host(evidence.source):
        reasons.append(f"the source host is outside the allowlist: {evidence.source}")

    # The titles match, when both are given. This applies to publications only:
    # for repository and framework evidence the two title fields carry a note of
    # a different kind, and comparing them would mean nothing.
    if evidence.type == "publication" and evidence.expected_title and evidence.actual_title:
        sim = _title_similarity(evidence.expected_title, evidence.actual_title)
        if sim < TITLE_SIMILARITY_THRESHOLD:
            reasons.append(
                f"the titles do not match: similarity {sim:.2f} is below "
                f"{TITLE_SIMILARITY_THRESHOLD}"
            )

    # Numeric values fall in an admissible range.
    #
    # A source can answer in perfect syntax and complete nonsense. Such an answer
    # is more dangerous than a refusal: a refusal is visible, whereas nonsense
    # looks like a result and reaches the maturity scale.
    #
    # The upper bound on the year is taken from the date of collection rather
    # than written in as a number. A written-in bound either rejects correct data
    # once time reaches it or, as this one did before the fix, admits the year
    # 2099 as plausible.
    val = evidence.value or ""
    for pattern, message in _NON_NEGATIVE:
        found = re.search(pattern, val)
        if found and float(found.group(1)) < 0:
            reasons.append(f"{message}: {found.group(1)}")

    max_year = evidence.fetched_at.year + 1
    for year_text in re.findall(r"year=(\d{4})", val) + re.findall(
        r"\((\d{4})\)", val
    ):
        year = int(year_text)
        if year < MIN_YEAR or year > max_year:
            reasons.append(
                f"the year of publication {year} is outside {MIN_YEAR}..{max_year}"
            )

    return CheckResult(passed=not reasons, reasons=reasons)


def check_many(evidence_list: list[RawEvidence]) -> list[tuple[RawEvidence, CheckResult]]:
    """Check a batch of evidence and return each item with its outcome."""
    return [(e, check(e)) for e in evidence_list]
