"""A release: the one irreversible action in this project.

Everything else can be rebuilt. A release cannot: it fixes a state for ever, a
link to it goes into somebody else's work, and its description is deposited in an
external archive and receives a permanent identifier. A mistake here is not
corrected, only explained.

Before this file existed, the release was covered by no test at all. Four ways to
release an untruth were found, and all four reproduced on the first try. A case
is built here for each.
"""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import make_release  # noqa: E402

from services.registry import store  # noqa: E402

TODAY = date(2026, 8, 11)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """The registry, the artefacts and the releases directory in a temporary place."""
    for name, path in (
        ("DATA_DIR", tmp_path / "data"),
        ("TECHNOLOGIES_DIR", tmp_path / "data" / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "data" / "evidence"),
        ("METRICS_DIR", tmp_path / "data" / "metrics"),
        ("LEVELS_FILE", tmp_path / "data" / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", tmp_path / "data" / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    (tmp_path / "data" / "technologies").mkdir(parents=True)

    artifacts = tmp_path / "public"
    artifacts.mkdir()
    monkeypatch.setattr(make_release, "ARTIFACTS", artifacts)
    monkeypatch.setattr(make_release, "RELEASES", artifacts / "releases")

    # There are several records, and the numbers of a release differ on purpose.
    # With one record they are all zero or one, and the check that the numbers
    # reach the description passes on any digit of the date, verifying nothing.
    for index, tech_id in enumerate(("alpha", "beta", "gamma")):
        store.save_technology(store.Technology(
            id=tech_id, name=tech_id.title(), kind="architecture", groups=["A"],
            configuration={"A4": "graph", "C1": "graph_traversal"},
            configuration_reviewed=TODAY if index < 2 else None,
        ))
    store.append_evidence([
        store.Evidence(
            technology_id=tech_id, type="publication",
            value=f"arXiv:{number}", source=f"https://arxiv.org/abs/{number}",
            fetched_at=TODAY, obtained_by="auto", verified=True,
        )
        for tech_id, number in (
            ("alpha", 1), ("alpha", 2), ("alpha", 3),
            ("beta", 4), ("beta", 5), ("gamma", 6), ("gamma", 7),
        )
    ])
    store.append_level(store.LevelEntry(
        technology_id="alpha", level="L1", confidence=0.5,
        rule_version="1.0.0", computed_at=TODAY,
    ))
    return tmp_path


def build_artifacts_now() -> None:
    """Build the artefacts into the substituted directory, as `make artifacts` does."""
    import build_artifacts

    build_artifacts.build(out_dir=make_release.artifacts_dir())


# ─── What gets frozen ────────────────────────────────────────────────────────


def test_release_refuses_stale_artifacts(workspace):
    """The numbers of a release come from the data, the files from the artefacts.

    The two were never compared, and the divergence was not theoretical: on a
    trial the snapshot claimed sixty-two technologies and held one. Such a release
    can neither be corrected nor withdrawn.
    """
    build_artifacts_now()
    store.save_technology(store.Technology(
        id="beta", name="Beta", kind="architecture", groups=["A"],
    ))

    problems = make_release.readiness()
    assert any("was not built from the current data" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1
    assert not (make_release.releases_dir() / TODAY.isoformat()).exists()


def test_release_refuses_unbuilt_artifacts(workspace):
    problems = make_release.readiness()
    assert any("the artefacts are not built" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1


def test_release_refuses_broken_data(workspace):
    """Spoiled data must not be fixed for ever.

    The release used to call no data validation at all.
    """
    build_artifacts_now()
    store.save_technology(store.Technology(
        id="alpha", name="Alpha", kind="architecture", groups=["A"],
        configuration={"A4": "hypercube"},
    ))
    problems = make_release.readiness()
    assert any("does not pass validation" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1


def test_snapshot_may_not_promise_a_file_it_lacks(workspace):
    """A missing snapshot file used to be copied in silence.

    The release listed it among its contents all the same, and the link to it led
    nowhere for ever.
    """
    build_artifacts_now()
    (make_release.artifacts_dir() / "residuals.json").unlink()

    meta = make_release.build(tag="trial", today=TODAY)
    with pytest.raises(FileNotFoundError, match="the snapshot is incomplete"):
        make_release.publish(meta)


# ─── The integrity of the write ──────────────────────────────────────────────


def test_interrupted_release_does_not_leave_half_of_one(workspace, monkeypatch):
    """An interruption leaves a draft rather than half a release.

    The directory under the tag appears already complete, because it is assembled
    beside its destination and moved in one stroke.
    """
    build_artifacts_now()
    meta = make_release.build(tag=TODAY.isoformat(), today=TODAY)

    def die(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(make_release.os, "replace", die)
    with pytest.raises(KeyboardInterrupt):
        make_release.publish(meta)

    target = make_release.releases_dir() / meta["tag"]
    assert not target.exists(), "half a release would stay for ever"
    leftovers = [p for p in make_release.releases_dir().iterdir() if p.is_dir()]
    assert leftovers == [], f"the draft was not removed: {leftovers}"


def test_incomplete_release_is_reported_not_accepted(workspace):
    """An empty directory under a tag does not count as a release.

    Existence of the directory used to be what was checked, so an interrupted
    release stayed empty for ever: a second attempt reported that it already
    existed, and the archive and the description were never created.
    """
    build_artifacts_now()
    (make_release.releases_dir() / TODAY.isoformat()).mkdir(parents=True)

    assert make_release.is_complete(TODAY.isoformat()) is False
    assert make_release.run(today=TODAY) == 1


@pytest.mark.parametrize("part", [
    "release.json", "registry.json", "residuals.json", "archive", "description",
    "index",
])
def test_any_missing_part_makes_the_release_incomplete(workspace, part):
    """Completeness is asked of each part separately.

    Checking one part would pass for checking the release, and the outcome would
    be the same: an empty directory fails on any of them.
    """
    build_artifacts_now()
    tag = TODAY.isoformat()
    make_release.run(today=TODAY)
    assert make_release.is_complete(tag) is True

    releases = make_release.releases_dir()
    if part == "archive":
        (releases / f"rag-world-{tag}.zip").unlink()
    elif part == "description":
        (releases / f"{tag}-deposit.json").unlink()
    elif part == "index":
        (releases / "index.json").write_text(
            json.dumps({"releases": []}), encoding="utf-8"
        )
    else:
        (releases / tag / part).unlink()

    assert make_release.is_complete(tag) is False, (
        f"a release missing the part «{part}» passed for complete"
    )


def test_published_release_is_never_rewritten(workspace):
    build_artifacts_now()
    meta = make_release.build(tag=TODAY.isoformat(), today=TODAY)
    make_release.publish(meta)
    with pytest.raises(FileExistsError):
        make_release.publish(meta)


def test_second_run_on_the_same_day_is_harmless(workspace):
    build_artifacts_now()
    assert make_release.run(today=TODAY) == 0
    before = sorted(p.name for p in make_release.releases_dir().iterdir())
    assert make_release.run(today=TODAY) == 0
    assert sorted(p.name for p in make_release.releases_dir().iterdir()) == before


def test_dry_run_writes_nothing(workspace):
    build_artifacts_now()
    assert make_release.run(today=TODAY, dry_run=True) == 0
    assert not make_release.releases_dir().exists()


# ─── The content of a release ────────────────────────────────────────────────


def test_release_numbers_match_its_own_files(workspace):
    """A release must not argue with itself.

    The same is compared on the published snapshot: the description is built from
    the same numbers and receives a permanent identifier.
    """
    build_artifacts_now()
    make_release.run(today=TODAY)

    target = make_release.releases_dir() / TODAY.isoformat()
    meta = json.loads((target / "release.json").read_text(encoding="utf-8"))
    registry = json.loads((target / "registry.json").read_text(encoding="utf-8"))
    rows = registry["technologies"] if isinstance(registry, dict) else registry

    assert meta["technologies"] == len(rows)
    assert meta["evidence"] == sum(r.get("evidence_count", 0) for r in rows)
    assert meta["reviewed"] == sum(1 for r in rows if r.get("configuration_reviewed"))
    assert meta["with_level"] == sum(1 for r in rows if r.get("level"))


def test_bundle_contains_every_file_the_release_promises(workspace):
    build_artifacts_now()
    make_release.run(today=TODAY)

    archive = make_release.releases_dir() / f"rag-world-{TODAY.isoformat()}.zip"
    inside = set(zipfile.ZipFile(archive).namelist())
    assert set(make_release.SNAPSHOT_FILES) <= inside
    assert "release.json" in inside


def test_deposit_description_repeats_the_release_numbers(workspace):
    """The description goes to an external archive and receives an identifier.

    Filling it in by hand on every release means eventually mistyping a number,
    and the numbers here are the content.
    """
    build_artifacts_now()
    make_release.run(today=TODAY)

    deposit = json.loads(
        (make_release.releases_dir() / f"{TODAY.isoformat()}-deposit.json")
        .read_text(encoding="utf-8")
    )
    meta = json.loads(
        (make_release.releases_dir() / TODAY.isoformat() / "release.json")
        .read_text(encoding="utf-8")
    )
    # Whole phrases are compared rather than bare numbers. A digit occurs in any
    # date, so a check by digit would pass on a description with every number
    # replaced.
    description = deposit["metadata"]["description"]
    for phrase in (
        f"Technologies recorded: {meta['technologies']}",
        f"evidence: {meta['evidence']}",
        f"computed for {meta['with_level']}",
        f"primary sources for {meta['reviewed']}",
    ):
        assert phrase in description, f"the description lacks the phrase «{phrase}»"
    assert deposit["metadata"]["version"] == meta["tag"]
    assert deposit["files"] == [f"rag-world-{TODAY.isoformat()}.zip"]


def test_index_lists_the_release_newest_first(workspace):
    build_artifacts_now()
    make_release.publish(make_release.build(tag="2026-08-01", today=date(2026, 8, 1)))
    make_release.publish(make_release.build(tag="2026-08-11", today=TODAY))

    assert [r["tag"] for r in make_release.releases_index()] == [
        "2026-08-11", "2026-08-01",
    ]
