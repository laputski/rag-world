"""A workflow must hold no logic.

Logic written into a job description is not covered by tests and cannot be run
locally: an error in it becomes visible only in a failing run, and sometimes not
even there. That happened once already — the diff parsing lived inside YAML and
decided whether to show a change to a person.

The rule: a job description invokes targets and scripts and computes nothing
itself.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

#: The marks of an embedded program: a body written straight into YAML, either a
#: heredoc or code in an argument. An ordinary invocation with flags
#: (`python -m pip install`) is not a program and must not be forbidden, or the
#: rule starts getting in the way.
EMBEDDED_INTERPRETER = re.compile(
    r"(python3?|node|ruby|perl)\s+-(c|e)\b|<<\s*[\"']?(PY|EOF|SCRIPT|PYTHON)\b",
    re.IGNORECASE,
)

#: Branching in the shell. A single check for "is there anything to commit" is
#: admissible, but the conditions must not multiply: that is the sign of logic
#: having moved in.
SHELL_BRANCH = re.compile(r"^\s*(if|case|while|for)\b", re.MULTILINE)
MAX_SHELL_BRANCHES = 2


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.exists() else []


def test_workflows_exist():
    assert _workflows(), "there are no workflows"


def test_no_embedded_programs():
    offenders = []
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        if EMBEDDED_INTERPRETER.search(text):
            offenders.append(path.name)
    assert not offenders, (
        "a program is written into a workflow: "
        + ", ".join(offenders)
        + ". Move it into scripts/ and cover it with tests."
    )


def test_shell_branching_stays_minimal():
    offenders = {}
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        count = len(SHELL_BRANCH.findall(text))
        if count > MAX_SHELL_BRANCHES:
            offenders[path.name] = count
    assert not offenders, (
        f"more than {MAX_SHELL_BRANCHES} shell branches: {offenders}. What to do "
        "is decided by a script, not by a job description."
    )


def test_update_workflow_calls_the_shared_entry_point():
    """The schedule runs exactly what a person runs."""
    text = (WORKFLOWS / "collect.yml").read_text(encoding="utf-8")
    assert "scripts/update.py" in text, (
        "the update pass must invoke the shared entry point scripts/update.py, "
        "or the unattended behaviour drifts from the local one"
    )


def test_review_gate_is_delegated_to_the_tested_script():
    text = (WORKFLOWS / "collect.yml").read_text(encoding="utf-8")
    assert "scripts/classify_changes.py" in text


def _update_steps() -> list[dict]:
    import yaml

    spec = yaml.safe_load((WORKFLOWS / "collect.yml").read_text(encoding="utf-8"))
    return spec["jobs"]["update"]["steps"]


def _run_log_steps() -> list[dict]:
    """The steps that record the run log."""
    return [
        step for step in _update_steps()
        if "collection_log.jsonl" in step.get("run", "")
    ]


def test_run_log_reaches_the_main_branch_on_every_pass():
    """The mark of a pass reaches the main branch always, with no condition.

    While it lay together with the data, a pass that went to review left nothing
    on the main branch. Two things broke in silence: the platform disables a
    schedule after sixty days without commits, and a reader tells "nobody looked"
    from "nothing happened" by the date of the last check.

    A condition on this step brings both back, so there is none.
    """
    steps = _run_log_steps()
    assert steps, (
        "no step records data/collection_log.jsonl: a pass that went to review "
        "would leave no trace on the main branch"
    )
    unconditional = [s for s in steps if "if" not in s]
    assert unconditional, (
        "the run log is recorded only under the condition "
        f"{[s.get('if') for s in steps]}. The mark of a pass is not a claim about a "
        "technology but a fact: there is nothing in it to review."
    )
    assert any("push" in s["run"] for s in unconditional), (
        "the mark of a pass is committed but not pushed: what serves as the sign "
        "of activity is precisely a pushed commit"
    )


def test_pushes_to_the_main_branch_rebase_first():
    """A push to the main branch happens after a rebase, not blind.

    The branch was checked out at the start of the pass, and in the minutes
    collection takes somebody else's commit may land on it. The push is then
    refused as a non-fast-forward, and what is lost is exactly what must always
    arrive: the mark of the pass. That is how this step first failed — the pass
    ran through and left no trace.
    """
    offenders = []
    for step in _update_steps():
        run = step.get("run", "")
        if "git push" not in run:
            continue
        # The review branch pushes its own new branch: nothing to collide with.
        if "checkout -b" in run:
            continue
        if "git pull --rebase" not in run:
            offenders.append(step.get("name", "unnamed"))
    assert not offenders, (
        f"steps push to the main branch without a rebase: {offenders}. Somebody "
        "else's commit between checkout and push undoes the whole pass."
    )


def test_review_branch_grows_from_the_recorded_pass():
    """The review branch grows from the recorded pass, not before it.

    Otherwise the run-log line enters the branch a second time and the merge hits
    a conflict on a file that holds nothing to conflict over.
    """
    steps = _update_steps()
    log = [i for i, s in enumerate(steps) if "collection_log.jsonl" in s.get("run", "")]
    branch = [i for i, s in enumerate(steps) if "checkout -b" in s.get("run", "")]
    assert log, "there is no step recording the run log"
    assert branch, "there is no step creating the review branch"
    log_at, branch_at = min(log), min(branch)
    assert log_at < branch_at, (
        "the review branch grows before the pass is recorded"
    )


def test_node_version_is_pinned_and_matches_ci():
    """The hosting platform and continuous integration build with the same Node.

    Without a pin the platform picks the version itself and may change it between
    two weekly deployments. A divergence from continuous integration is doubly
    dangerous: the build passes here and fails there.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    pinned = (root / "ui" / ".nvmrc").read_text(encoding="utf-8").strip()
    assert pinned, "the Node version is not pinned: ui/.nvmrc is empty"

    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    found = re.search(r'node-version:\s*"?(\d+)"?', ci)
    assert found, "the workflow does not name a Node version"
    assert found.group(1) == pinned.lstrip("v").split(".")[0], (
        f"the platform builds with Node {pinned} and CI with {found}"
    )
