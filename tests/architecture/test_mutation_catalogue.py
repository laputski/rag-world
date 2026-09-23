"""The mutation catalogue must not rot between runs.

A mutation run takes about ten minutes and is therefore started separately
rather than on every edit. Hence the danger: the code changes, an entry's pattern
stops matching, and the entry quietly stops checking anything. The catalogue
looks impressive meanwhile and stays green, because nobody has run it.

That happened three times in one day, so the integrity of the catalogue is
checked here, in the ordinary suite. The check is instant: it runs no mutant at
all and only verifies that each has somewhere to apply.

The split is deliberate. The expensive part, the run itself, goes on a schedule;
the cheap part, the soundness of the catalogue, runs on every edit, because edits
are what spoil it.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mutate  # noqa: E402


def _applied_by_the_run(mutation: mutate.Mutation) -> bool:
    """Whether the mutation run has applied this entry to the tree right now.

    The pattern of that entry is then absent by construction, and judging it
    would kill every mutant for a reason of this file's own. See
    `mutate.MUTANT_ENV` for what that cost.
    """
    return os.environ.get(mutate.MUTANT_ENV) == mutation.ident


@pytest.mark.parametrize("mutation", mutate.MUTATIONS, ids=lambda m: m.ident)
def test_every_mutation_still_applies(mutation):
    """An entry's pattern still occurs in the code it guards."""
    if _applied_by_the_run(mutation):
        pytest.skip("this entry is applied by the mutation run itself")
    target = ROOT / mutation.path
    assert target.exists(), f"the file {mutation.path} does not exist"
    source = target.read_text(encoding="utf-8")
    assert mutation.before in source, (
        f"the pattern of the entry «{mutation.rule}» no longer occurs in "
        f"{mutation.path}. The entry checks nothing while staying in the catalogue "
        "and creating an appearance of a guard: fix the pattern or remove the entry."
    )


@pytest.mark.parametrize("mutation", mutate.MUTATIONS, ids=lambda m: m.ident)
def test_every_mutation_actually_changes_something(mutation):
    """A break has to change the code, or the run checks nothing."""
    if _applied_by_the_run(mutation):
        pytest.skip("this entry is applied by the mutation run itself")
    assert mutation.before != mutation.after, f"«{mutation.rule}» changes nothing"
    source = (ROOT / mutation.path).read_text(encoding="utf-8")
    assert source.replace(mutation.before, mutation.after, 1) != source


# ─── What the unattended pass rewrites ───────────────────────────────────────

#: The workflow of the weekly pass. What it stages is what it may rewrite.
COLLECT_WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"

ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _paths_the_pass_commits() -> set[str]:
    """The paths named by the pass's own `git add` commands.

    Taken from the workflow rather than written down here: a list kept beside
    the workflow would drift from it, and the first file forgotten would be the
    one that breaks.
    """
    text = COLLECT_WORKFLOW.read_text(encoding="utf-8")
    paths: set[str] = set()
    for line in re.findall(r"git add ([^\n]+)", text):
        paths.update(line.split())
    return paths


def _pins_a_date_the_pass_moves(mutation: mutate.Mutation, committed: set[str]) -> bool:
    written = any(
        mutation.path == path or mutation.path.startswith(path.rstrip("/") + "/")
        for path in committed
    )
    return written and bool(ISO_DATE.search(mutation.before))


def test_the_workflow_still_names_what_it_commits():
    """The rule below reads the workflow; an empty reading would pass everything."""
    assert {"data", "ui/public"} <= _paths_the_pass_commits()


def test_the_historical_breakage_is_recognised():
    """The bait: the entry as it stood when the pass broke it on 2026-09-14."""
    broken = mutate.Mutation(
        "data/technologies/standard_hybridrag.json",
        "the real data is validated by the test run",
        '"verified_at": "2026-08-13"', '"verified_at": null',
    )
    assert _pins_a_date_the_pass_moves(broken, _paths_the_pass_commits())


def test_no_entry_pins_a_date_in_what_the_pass_commits():
    """A date in a file the pass commits is the thing the pass moves.

    On 2026-09-14 the link check rewrote the check date an entry was anchored
    to. Two tests of this catalogue went red on nobody's edit, and the scheduled
    mutation run of 2026-09-17 refused to start, because the suite did not pass
    on the untouched tree. Nothing in the pass runs the suite, so the breakage
    waited three days to be seen.

    The rule is narrower than the danger. The pass also rewrites marks and
    scores that carry no date, and those this test does not see. A date is
    singled out because it is what broke, and because every date the pass
    writes means "when this was last looked at", which is exactly the kind of
    value that moves on its own.
    """
    committed = _paths_the_pass_commits()
    pinned = [
        f"{m.path}: «{m.rule}»"
        for m in mutate.MUTATIONS
        if _pins_a_date_the_pass_moves(m, committed)
    ]
    assert not pinned, (
        "entries anchored to a date in a file the weekly pass commits; the pass "
        "will move the date and the entry will stop applying:\n  "
        + "\n  ".join(pinned)
    )


def test_the_bait_for_real_data_is_seen_by_the_validation_alone(
    tmp_path, monkeypatch
):
    """The entry for real data proves the validation runs, and nothing else.

    The mutation run asks only whether some test notices a mutant. For this
    entry that is not enough: the comparison of the published artefacts notices
    most edits to the data, so a bait it can see stays caught when the
    validation test is deleted, and the entry keeps reporting a guard that is
    gone. That was the state of the entry before 2026-09-22.

    So the bait is held to two conditions, on a copy of the data: the
    validation names it, and a build of the artefacts cannot tell it from the
    untouched data.
    """
    import shutil

    import validate_data

    from scripts.build_artifacts import build
    from services.registry import store

    entry = next(
        m for m in mutate.MUTATIONS
        if m.rule == "the real data is validated by the test run"
    )
    assert entry.path.startswith("data/"), "the bait must lie in the real data"

    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    for name, path in (
        ("DATA_DIR", data),
        ("TECHNOLOGIES_DIR", data / "technologies"),
        ("EVIDENCE_DIR", data / "evidence"),
        ("METRICS_DIR", data / "metrics"),
        ("LEVELS_FILE", data / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", data / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)

    # The premise is data that passes. When it does not, the contract test says
    # so, and failing here as well would kill the mutant of that very entry for
    # a reason of this test's own.
    if validate_data.check_registry():
        pytest.skip("the real data does not pass validation; its own test reports that")
    untouched = tmp_path / "untouched" / "data"
    build(out_dir=untouched)

    target = data / entry.path.removeprefix("data/")
    source = target.read_text(encoding="utf-8")
    target.write_text(source.replace(entry.before, entry.after, 1), encoding="utf-8")

    problems = validate_data.check_registry()
    assert problems, "the validation does not see the bait"

    mutated = tmp_path / "mutated" / "data"
    build(out_dir=mutated)
    differing = sorted(
        str(path.relative_to(mutated.parent))
        for path in mutated.parent.rglob("*")
        if path.is_file()
        and path.read_bytes()
        != (untouched.parent / path.relative_to(mutated.parent)).read_bytes()
    )
    assert not differing, (
        "the artefacts change under the bait, so their comparison catches it "
        f"too and the entry proves nothing about the validation: {differing}"
    )


def test_rules_are_named_distinctly():
    """Identical names make the report unreadable: which one survived?"""
    names = [m.rule for m in mutate.MUTATIONS]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"repeated rule names: {duplicates}"


def test_catalogue_covers_the_load_bearing_modules():
    """The catalogue covers what the unattended pass rests on.

    The list is short and deliberately incomplete: it names the places whose
    absence from the catalogue would mean the run is not looking at the main
    thing.
    """
    covered = {m.path for m in mutate.MUTATIONS}
    for path in (
        "core/maturity.py",
        "scripts/validate_data.py",
        "scripts/classify_changes.py",
        "scripts/make_release.py",
        "scripts/check_links.py",
        "services/registry/store.py",
    ):
        assert path in covered, f"{path} is covered by no mutation"


# ─── The run itself ──────────────────────────────────────────────────────────


def test_the_run_names_its_mutant_to_the_suite(monkeypatch):
    """The suite is told which entry is applied, and told nothing on a clean tree."""
    seen: list[dict] = []

    def record(*args, **kwargs):
        seen.append(kwargs["env"])
        return None

    monkeypatch.setattr(mutate.subprocess, "run", record)
    monkeypatch.setenv(mutate.MUTANT_ENV, "left over from an outer run")
    entry = mutate.MUTATIONS[0]

    mutate._pytest(entry)
    mutate._pytest()

    assert seen[0][mutate.MUTANT_ENV] == entry.ident
    assert mutate.MUTANT_ENV not in seen[1], (
        "the untouched tree is checked with a mutant's name in the environment"
    )


def test_an_applied_entry_is_left_to_the_tests_of_its_rule(monkeypatch):
    """The bait: an entry whose pattern is gone, as it is while the run applies it.

    Unnamed, it fails the catalogue's test, which is right between runs. Named
    by the run, it is skipped, so that only a test of the rule can kill it.
    """
    gone = mutate.Mutation("scripts/mutate.py", "a pattern that is gone",
                           "no such text anywhere in the file", "other text")

    monkeypatch.delenv(mutate.MUTANT_ENV, raising=False)
    with pytest.raises(AssertionError):
        test_every_mutation_still_applies(gone)

    monkeypatch.setenv(mutate.MUTANT_ENV, gone.ident)
    with pytest.raises(pytest.skip.Exception):
        test_every_mutation_still_applies(gone)
    with pytest.raises(pytest.skip.Exception):
        test_every_mutation_actually_changes_something(gone)



def test_absent_pattern_is_reported_not_skipped(tmp_path, monkeypatch):
    """A mutant that did not apply differs from one caught and one survived.

    A skip would look like a success, and that is exactly the case the check above
    exists for.
    """
    sample = tmp_path / "sample.py"
    sample.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    absent = mutate.Mutation("sample.py", "what is absent", "no such text", "other")
    assert mutate.survives(absent) is None


def test_file_is_restored_even_when_the_run_blows_up(tmp_path, monkeypatch):
    """A break must not outlive the run under any outcome.

    An interrupt from the keyboard mid-run would otherwise leave the working code
    broken in the tree.
    """
    sample = tmp_path / "sample.py"
    original = "value = 1\n"
    sample.write_text(original, encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    def boom(mutation=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(mutate, "_pytest", boom)
    with pytest.raises(KeyboardInterrupt):
        mutate.survives(mutate.Mutation("sample.py", "a rule", "1", "2"))

    assert sample.read_text(encoding="utf-8") == original


def test_the_run_leaves_no_compiled_mutant_behind():
    """A mutant must not survive in the bytecode cache.

    Python calls a cached `.pyc` current by the source's modification time and
    size. A mutation that keeps the size and is restored within the same second
    leaves a cache both checks accept, and the next run executes the mutant while
    the source on disk is sound.

    That is the worst shape a failure can take here: the suite goes green over
    broken bytecode, and whatever it writes is written by the mutant. It happened
    once, and the candidate queue was rewritten with scores a mutant computed.
    """
    source = (ROOT / "scripts" / "mutate.py").read_text(encoding="utf-8")
    assert "PYTHONDONTWRITEBYTECODE" in source, (
        "the mutation run writes bytecode; a restored file can then be read from "
        "a mutant's cache"
    )
