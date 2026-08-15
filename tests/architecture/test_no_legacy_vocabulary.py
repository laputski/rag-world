"""The vocabulary guard: an abandoned model must not return to the project.

The earlier factorisation of RAG into "seven orthogonal axes" was reversed: the
single contract is twenty-eight dimensions in seven strata. This test does not
let the abandoned model seep back into the code, the texts or the data.

The rules are deliberately precise. What is forbidden are the **identifiers** of
the abandoned model and its **named phrases**, not the English word `axis` by
itself: charts have axes (`xAxis`, `yAxis`), and `d3-axis` is a real build
dependency. For the same reason the Russian word for "axis" is not forbidden: the
maturity map has two of them and they have to be written about.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Directories that are not sources of this project.
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".idea", ".zcode", ".deepeval", "dist", "build",
    "rag_constructor.egg-info", "rag_world.egg-info",
}

# Files whose content we do not write (the names of third-party packages), and
# the guard itself: it has to list what is forbidden in order to look for it.
SKIP_FILES = {"package-lock.json", "package.json", "test_no_legacy_vocabulary.py"}

SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json",
    ".yml", ".yaml", ".sql", ".toml", ".html", ".css",
}

# The identifiers of the abandoned model: they occur only in its own code.
FORBIDDEN_IDENTIFIERS = (
    "AxisCoordinates",
    "AxesResponse",
    "AXIS_VALUES",
    "AXIS_TO_KIND",
    "AXIS_VALUE_TO_DIMENSIONS",
    "AXES_TO_DIMENSIONS",
    "blocked_axis_values",
    "config_hash_v1",
    "getAxes",
    "preset_coords",
    "pre_retrieval",
)

# The named phrases of the abandoned model, in both languages.
FORBIDDEN_PHRASES = (
    r"семиосев\w*",
    r"ортогональн\w*",
    r"\b7\s*осей\b",
    r"\bсем[ьи]\s+осей\b",
    r"\b7\s*[- ]?осев\w*",
    r"\b7\s*сло[ёе]в\b",
    r"\bсем[ьи]\s+сло[ёе]в\b",
    r"\bсемисло\w*",
    r"\bос(?:ь|и|ей|ям|ями|ях)\s+конструктора\b",
    r"\bосева\w+\s+модел\w+",
    r"\bseven[- ]ax[ei]s\w*",
    r"\bseven[- ]layer\w*",
    r"\b7[- ]ax[ei]s\w*",
    r"\borthogonal\s+ax[ei]s\b",
)

PATTERN = re.compile(
    "|".join(
        [re.escape(i) for i in FORBIDDEN_IDENTIFIERS] + list(FORBIDDEN_PHRASES)
    ),
    re.IGNORECASE,
)

# Files awaiting a rewrite in later phases. The list must shrink: the test fails
# when a file in it is already clean, so that an entry does not hang around after
# the work is done.
# It is empty: the last file on the list was worked through and deleted. The real
# names became registry records and the rest were refused with a reason in
# data/rejected.jsonl. The registry is once again the only place technologies
# live.
PENDING_REWRITE: frozenset[str] = frozenset()


def _iter_source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in SUFFIXES and path.name != "Makefile":
            continue
        yield rel, path


def _violations(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [m.group(0) for m in PATTERN.finditer(text)]


def test_legacy_vocabulary_absent_from_project():
    """No file outside the pending list carries the old vocabulary."""
    offenders: dict[str, list[str]] = {}
    for rel, path in _iter_source_files():
        key = rel.as_posix()
        if key in PENDING_REWRITE:
            continue
        found = _violations(path)
        if found:
            offenders[key] = sorted(set(found))[:5]
    assert not offenders, (
        "The vocabulary of the abandoned model has returned to the project:\n"
        + "\n".join(f"  {k}: {', '.join(v)}" for k, v in sorted(offenders.items()))
    )


def test_pending_rewrite_list_only_shrinks():
    """An entry stays on the list only while the file is genuinely not clean."""
    stale = []
    for name in sorted(PENDING_REWRITE):
        path = ROOT / name
        if not path.exists():
            continue  # the file is gone; the entry goes with the next edit
        if not _violations(path):
            stale.append(name)
    assert not stale, (
        "These files are already clean — remove them from PENDING_REWRITE:\n  "
        + "\n  ".join(stale)
    )


def test_replacement_model_is_declared():
    """The abandoned model was replaced rather than merely deleted."""
    from core.dimensions_schema import DIMENSIONS, STRATA

    assert len(STRATA) == 7, "seven strata are expected"
    assert len(DIMENSIONS) == 28, "twenty-eight dimensions are expected"
