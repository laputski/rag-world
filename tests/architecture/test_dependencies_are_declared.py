"""Всё, что код ввозит, должно быть объявлено зависимостью.

Отказ здесь особенно неприятен тем, что локально его не видно. Пакет приходит
попутно с другим, разработчик пишет `import`, проверки у него зелёные, а на
чистой установке набор падает. Именно так и вышло: разбор описаний рабочих
процессов ввозил `yaml`, локально пришедший с чем-то ещё, и непрерывная
интеграция упала на первом же прогоне после отправки.

Проверка сравнивает то, что код действительно ввозит, с тем, что объявлено в
`pyproject.toml`, и делает это по разбору исходников, а не по установленному
окружению: окружение и есть то, что врёт.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

#: Каталоги, чьи ввозы обязаны быть обеспечены объявленными зависимостями.
WATCHED = ("core", "services", "scripts", "tests")

#: Модули стандартной библиотеки ввозить можно без объявления.
STDLIB = set(sys.stdlib_module_names)

#: Имя пакета в объявлении не всегда совпадает с именем ввозимого модуля.
DISTRIBUTION = {
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
}


def _declared() -> set[str]:
    """Имена пакетов из pyproject: и обязательных, и для разработки."""
    import re

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    names = set()
    for match in re.finditer(r'"([A-Za-z][\w.\-]*)\s*(?:\[[^\]]*\])?\s*[<>=!~]', text):
        names.add(match.group(1).lower().replace("_", "-"))
    return names


def _own_modules() -> set[str]:
    """Свои модули, включая те, что ввозятся по короткому имени.

    Точки входа лежат в `scripts/` и добавляют этот каталог в путь поиска,
    поэтому друг друга они ввозят как `import build_artifacts`. Для проверки
    это свой код, а не сторонний пакет.
    """
    own = {"core", "services", "scripts", "tests"}
    for folder in ("scripts", "core", "services"):
        for path in (ROOT / folder).rglob("*.py"):
            if "__pycache__" not in str(path):
                own.add(path.stem)
    return own


def _imported() -> dict[str, set[str]]:
    """Ввозимые сторонние модули и файлы, где они встретились."""
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
                    # Относительный ввоз своего же кода объявления не требует.
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
        "код ввозит пакеты, не объявленные в pyproject.toml: "
        f"{missing}. Локально они могли прийти попутно с другими, а на чистой "
        "установке набор упадёт."
    )


def test_workflow_parser_dependency_is_declared():
    """Отдельно назван тот случай, ради которого проверка заведена."""
    assert "pyyaml" in _declared(), (
        "разбор описаний рабочих процессов ввозит yaml; без объявления "
        "непрерывная интеграция падает на чистой установке"
    )
