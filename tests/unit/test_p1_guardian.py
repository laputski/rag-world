"""C1 guardian: core/ must be domain-neutral.

Scans core/ .py files via AST for domain-specific IDENTIFIERS (field names,
class names, function names, assignments). Comments and docstrings are NOT
scanned — they may legitimately mention domains as examples (e.g. "a legal
corpus fills ref_code with..."). Domain specialization lives in components/
or future domain_packs/.

Mirrors virtaul-assistant's tests/unit/test_p1_guardian.py intent (C1).
"""

import ast
from pathlib import Path

# Identifier substrings that indicate a domain leak into the neutral core.
# Matched against names (field/class/func/var), never against string literals
# or comments, so docstring examples like "legal corpus" don't trip it.
FORBIDDEN_ID_PATTERNS = [
    # legal
    "legal", "law", "statute", "article_no", "act_kind", "decree", "edict",
    "npa", "pravo", "jurisdiction",
    # medical
    "medical", "patient", "diagnosis", "clinical", "hospital",
    # automotive
    "automotive", "vehicle",
]

CORE_DIR = Path(__file__).resolve().parents[2] / "core"


def _collect_identifiers(tree: ast.AST) -> list[str]:
    """Extract identifier names from an AST (names, not string literals)."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.Attribute) and node.attr:
            names.append(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
        # ast.keyword.arg (kwargs) — captured as Attribute/Name in most cases.
        elif isinstance(node, ast.keyword) and node.arg:
            names.append(node.arg)
    return [n for n in names if isinstance(n, str)]


def _scan_file(path: Path) -> list[str]:
    """Return forbidden patterns found among the file's identifiers."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    ids = {name.lower() for name in _collect_identifiers(tree)}
    hits: list[str] = []
    for pat in FORBIDDEN_ID_PATTERNS:
        if any(pat in ident for ident in ids):
            hits.append(pat)
    return hits


def test_core_contains_no_domain_identifiers():
    offenders: dict[str, list[str]] = {}
    for py in CORE_DIR.rglob("*.py"):
        hits = _scan_file(py)
        if hits:
            offenders[str(py.relative_to(CORE_DIR.parent))] = sorted(set(hits))
    assert not offenders, (
        "C1 violation: domain identifiers found in core/ (must be domain-neutral):\n"
        + "\n".join(f"  {f}: {t}" for f, t in offenders.items())
    )


def test_core_directory_exists():
    assert CORE_DIR.is_dir(), f"core/ not found at {CORE_DIR}"
