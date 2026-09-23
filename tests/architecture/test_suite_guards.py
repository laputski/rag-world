"""The guards of the suite fire, and the mutation run tells a write from a catch.

Two autouse fixtures in `tests/conftest.py` fail the suite when a test writes
into the real data or reaches for the network. A guard that never fires looks
exactly like one that works, so each is baited here: an inner run of pytest
loads the same configuration, a test in it commits the offence, and the inner
run must fail with the guard's own words. The data directory of the inner run
is a temporary one, so proving the guard writes nothing real.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import mutate  # noqa: E402

from tests.conftest import NETWORK_REACHED, REAL_DATA_WRITTEN  # noqa: E402

OFFENCES = '''
import os
from pathlib import Path


def test_writes_the_data():
    root = Path(os.environ["RAG_WORLD_GUARD_ROOT"])
    (root / "data" / "written.jsonl").write_text("{}\\n", encoding="utf-8")


def test_reaches_for_the_network():
    import requests
    try:
        requests.get("https://example.org/", timeout=1)
    except requests.ConnectionError:
        pass  # the code under test swallows it, as the link check does
'''


def _inner_run(tmp_path: Path, test: str) -> subprocess.CompletedProcess:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "test_offences.py").write_text(OFFENCES, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.conftest",
         "-p", "no:cacheprovider", f"{tmp_path / 'test_offences.py'}::{test}"],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "RAG_WORLD_GUARD_ROOT": str(tmp_path),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_a_write_into_the_data_fails_the_suite(tmp_path):
    result = _inner_run(tmp_path, "test_writes_the_data")
    assert result.returncode != 0, result.stdout[-500:]
    assert REAL_DATA_WRITTEN in result.stdout
    assert "data/written.jsonl" in result.stdout


def test_a_swallowed_request_fails_the_test(tmp_path):
    result = _inner_run(tmp_path, "test_reaches_for_the_network")
    assert result.returncode != 0, result.stdout[-500:]
    assert NETWORK_REACHED in result.stdout
    assert "https://example.org/" in result.stdout


# ─── The mutation run ────────────────────────────────────────────────────────


def _tree(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "queue.jsonl").write_text('{"score": 0}\n', encoding="utf-8")
    (tmp_path / "rule.py").write_text("SCORE = 0\n", encoding="utf-8")
    monkeypatch.setattr(mutate, "ROOT", tmp_path)
    return tmp_path


def test_a_mutant_whose_run_writes_the_data_is_no_catch(tmp_path, monkeypatch):
    """The bait: the suite, run against the mutant, rescored the queue.

    That is what happened on 2026-09-22, and every later mutant was killed by
    the broken queue. The run must put the file back and say what happened.
    """
    root = _tree(tmp_path, monkeypatch)
    queue = root / "data" / "queue.jsonl"

    def suite_that_writes(mutation=None):
        queue.write_text('{"score": -1}\n', encoding="utf-8")
        return subprocess.CompletedProcess([], 1)

    monkeypatch.setattr(mutate, "_pytest", suite_that_writes)
    entry = mutate.Mutation("rule.py", "a rule", "SCORE = 0", "SCORE = -1")

    try:
        mutate.survives(entry)
    except mutate.WroteRealData as written:
        assert written.paths == [queue]
    else:
        raise AssertionError("a run that wrote the data was counted as a verdict")
    assert queue.read_text(encoding="utf-8") == '{"score": 0}\n', "not put back"
    assert (root / "rule.py").read_text(encoding="utf-8") == "SCORE = 0\n"


def test_a_mutant_whose_run_writes_nothing_gets_its_verdict(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch)
    monkeypatch.setattr(
        mutate, "_pytest", lambda mutation=None: subprocess.CompletedProcess([], 1)
    )
    entry = mutate.Mutation("rule.py", "a rule", "SCORE = 0", "SCORE = -1")
    assert mutate.survives(entry) is False


# ─── Paths fixed at import ───────────────────────────────────────────────────


def test_no_script_fixes_a_data_path_at_import():
    """A path into the data is read when it is used, never when a module loads.

    A constant computed from the store's data directory at import follows no
    later substitution of that directory. Discovery held two, and the end-to-end
    test of the pass read and rescored the real candidate queue from inside a
    test believed to be isolated. A check of the values such constants hold
    cannot find them reliably: a module first imported inside another test's
    substitution holds that test's directory and looks correct. So the source
    is read instead, and such a constant is refused outright.
    """
    import re

    fixed = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*store\.DATA_DIR\b", re.MULTILINE)
    found = [
        f"{path.relative_to(ROOT)}: {name}"
        for path in sorted((ROOT / "scripts").glob("*.py"))
        for name in fixed.findall(path.read_text(encoding="utf-8"))
    ]
    assert not found, f"data paths fixed at import: {found}"


def test_the_reading_recognises_a_fixed_path():
    """The bait: the shape discovery had before 2026-09-22 is recognised."""
    import re

    fixed = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*store\.DATA_DIR\b", re.MULTILINE)
    assert fixed.findall('CANDIDATES = store.DATA_DIR / "candidates.jsonl"\n') == ["CANDIDATES"]
