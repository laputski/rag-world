"""Рабочие процессы не должны содержать логику.

Логика, вписанная в описание задания, не проверяется тестами и не запускается
локально: увидеть её ошибку можно только в неудачном прогоне, а иногда нельзя
и там. Так уже случилось однажды — разбор изменений жил внутри YAML и решал,
показывать ли изменение человеку.

Правило: описание задания вызывает цели и скрипты, но само ничего не вычисляет.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

#: Признаки вложенной программы: тело прямо в YAML. Это либо heredoc, либо
#: код в аргументе. Обычный вызов с флагами (`python -m pip install`) программой
#: не является и запрещаться не должен — иначе правило начнёт мешать.
EMBEDDED_INTERPRETER = re.compile(
    r"(python3?|node|ruby|perl)\s+-(c|e)\b|<<\s*[\"']?(PY|EOF|SCRIPT|PYTHON)\b",
    re.IGNORECASE,
)

#: Ветвление в оболочке. Одиночная проверка «есть ли изменения» допустима,
#: но условий не должно становиться много: это признак переехавшей логики.
SHELL_BRANCH = re.compile(r"^\s*(if|case|while|for)\b", re.MULTILINE)
MAX_SHELL_BRANCHES = 2


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.exists() else []


def test_workflows_exist():
    assert _workflows(), "рабочие процессы отсутствуют"


def test_no_embedded_programs():
    offenders = []
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        if EMBEDDED_INTERPRETER.search(text):
            offenders.append(path.name)
    assert not offenders, (
        "в рабочий процесс вписана программа: "
        + ", ".join(offenders)
        + ". Вынесите её в scripts/ и покройте тестами."
    )


def test_shell_branching_stays_minimal():
    offenders = {}
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        count = len(SHELL_BRANCH.findall(text))
        if count > MAX_SHELL_BRANCHES:
            offenders[path.name] = count
    assert not offenders, (
        f"ветвлений в оболочке больше {MAX_SHELL_BRANCHES}: {offenders}. "
        "Решение о том, что делать, принимает скрипт, а не описание задания."
    )


def test_update_workflow_calls_the_shared_entry_point():
    """Расписание запускает ровно то же, что и человек."""
    text = (WORKFLOWS / "collect.yml").read_text(encoding="utf-8")
    assert "scripts/update.py" in text, (
        "проход обновления должен вызывать общую точку входа, "
        "иначе автономное поведение разойдётся с локальным"
    )


def test_review_gate_is_delegated_to_the_tested_script():
    text = (WORKFLOWS / "collect.yml").read_text(encoding="utf-8")
    assert "scripts/classify_changes.py" in text


def test_node_version_is_pinned_and_matches_ci():
    """Площадка и непрерывная интеграция должны собирать одним и тем же Node.

    Без закрепления версию выбирает площадка, и её обновление ломает
    еженедельное развёртывание в момент, когда никто не смотрит. Расхождение с
    интеграцией опаснее вдвойне: проверки зелёные, а сборка на площадке падает.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    pinned = (root / "ui" / ".nvmrc").read_text(encoding="utf-8").strip()
    assert pinned, "версия Node не закреплена: ui/.nvmrc пуст"

    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    found = re.search(r'node-version:\s*"?(\d+)"?', ci)
    assert found, "в рабочем процессе не указана версия Node"
    assert found.group(1) == pinned.lstrip("v").split(".")[0], (
        f"площадка собирает Node {pinned}, интеграция — {found.group(1)}"
    )
