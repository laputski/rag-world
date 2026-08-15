"""The mutation catalogue must not rot between runs.

A mutation run takes twenty-odd minutes and is therefore started separately
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

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mutate  # noqa: E402


@pytest.mark.parametrize(
    "mutation", mutate.MUTATIONS, ids=lambda m: f"{m.path}::{m.rule}"
)
def test_every_mutation_still_applies(mutation):
    """An entry's pattern still occurs in the code it guards."""
    target = ROOT / mutation.path
    assert target.exists(), f"the file {mutation.path} does not exist"
    source = target.read_text(encoding="utf-8")
    assert mutation.before in source, (
        f"the pattern of the entry «{mutation.rule}» no longer occurs in "
        f"{mutation.path}. The entry checks nothing while staying in the catalogue "
        "and creating an appearance of a guard: fix the pattern or remove the entry."
    )


@pytest.mark.parametrize(
    "mutation", mutate.MUTATIONS, ids=lambda m: f"{m.path}::{m.rule}"
)
def test_every_mutation_actually_changes_something(mutation):
    """A break has to change the code, or the run checks nothing."""
    assert mutation.before != mutation.after, f"«{mutation.rule}» changes nothing"
    source = (ROOT / mutation.path).read_text(encoding="utf-8")
    assert source.replace(mutation.before, mutation.after, 1) != source


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


def test_absent_pattern_is_reported_not_skipped(tmp_path, monkeypatch):
    """A mutant that did not apply differs from one caught and one survived.

    A skip would look like a success, and that is exactly the case the check above
    exists for.
    """
    sample = tmp_path / "sample.py"
    sample.write_text("значение = 1\n", encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    absent = mutate.Mutation("sample.py", "what is absent", "no such text", "other")
    assert mutate.survives(absent) is None


def test_file_is_restored_even_when_the_run_blows_up(tmp_path, monkeypatch):
    """A break must not outlive the run under any outcome.

    An interrupt from the keyboard mid-run would otherwise leave the working code
    broken in the tree.
    """
    sample = tmp_path / "sample.py"
    original = "значение = 1\n"
    sample.write_text(original, encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)

    def boom():
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
