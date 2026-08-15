"""Everything the code imports has to be declared as a dependency.

A failure here is especially unpleasant because it is invisible locally. A
package arrives alongside another, the developer writes an `import`, their checks
are green, and on a clean install the suite fails. That is exactly what happened:
the workflow parser imported `yaml`, which locally came in with something else,
and continuous integration failed on the first run after a push.

The check compares what the code actually imports with what `pyproject.toml`
declares, and it does so by parsing the sources rather than by inspecting the
installed environment: the environment is the thing that lies.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

#: The directories whose imports must be covered by declared dependencies.
WATCHED = ("core", "services", "scripts", "tests")

#: Standard-library modules may be imported without a declaration.
STDLIB = set(sys.stdlib_module_names)

#: The declared package name does not always match the imported module name.
DISTRIBUTION = {
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
}


def _declared() -> set[str]:
    """The package names from pyproject, both required and development ones."""
    import re

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    names = set()
    for match in re.finditer(r'"([A-Za-z][\w.\-]*)\s*(?:\[[^\]]*\])?\s*[<>=!~]', text):
        names.add(match.group(1).lower().replace("_", "-"))
    return names


def _own_modules() -> set[str]:
    """The project's own modules, including those imported by a short name.

    The entry points live in `scripts/` and add that directory to the search path,
    so they import one another as `import build_artifacts`. For this check that is
    the project's own code and not a third-party package.
    """
    own = {"core", "services", "scripts", "tests"}
    for folder in ("scripts", "core", "services"):
        for path in (ROOT / folder).rglob("*.py"):
            if "__pycache__" not in str(path):
                own.add(path.stem)
    return own


def _imported() -> dict[str, set[str]]:
    """The third-party modules imported, and the files they appear in."""
    found: dict[str, set[str]] = {}
    own = _own_modules()
    for folder in WATCHED:
        for path in sorted((ROOT / folder).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    # A relative import of the project's own code needs no
                    # declaration.
                    modules = [node.module] if node.level == 0 and node.module else []
                else:
                    continue
                for module in modules:
                    top = module.split(".")[0]
                    if top in STDLIB or top in own or top.startswith("_"):
                        continue
                    found.setdefault(top, set()).add(
                        str(path.relative_to(ROOT))
                    )
    return found


def test_every_third_party_import_is_declared():
    declared = _declared()
    missing = {
        module: sorted(where)
        for module, where in _imported().items()
        if DISTRIBUTION.get(module, module).lower().replace("_", "-") not in declared
    }
    assert not missing, (
        "the code imports packages not declared in pyproject.toml: "
        f"{missing}. Locally they may have arrived alongside others, and on a "
        "clean install the suite will fail."
    )


def test_workflow_parser_dependency_is_declared():
    """The case this check was created for is named outright."""
    assert "pyyaml" in _declared(), (
        "the workflow parser imports yaml; without a declaration continuous "
        "integration fails on a clean install"
    )
