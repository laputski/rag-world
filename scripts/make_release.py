#!/usr/bin/env python3
"""Release the registry: a snapshot that can be cited.

Scholars do not cite web sites. A site changes, and the citation stops
supporting what it was given for: the reader opens it and sees something else.
What gets cited is something that has a version.

A release is a dated snapshot of the artefacts. It is placed beside them under
its own tag and is **never rewritten**, which is the whole point. A link of the
form `/data/releases/2026-08-10/registry.json` will return in a year what it
returns today, even if the registry has doubled in the meantime.

A record has no identifier of its own and will not get one. A record changes,
and a permanent identifier for a changing object misleads more than its absence
does: the link looks dependable while pointing at a moving target. What should
be cited is a record **in a release**.

Usage::

    python3 scripts/make_release.py            # release a snapshot of today
    python3 scripts/make_release.py --dry-run  # show what the release would hold
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "ui" / "public" / "data"
RELEASES = ARTIFACTS / "releases"

#: What goes into a snapshot. The feed does not: it is about news, not state.
SNAPSHOT_FILES = ("registry.json", "map.json", "stats.json", "residuals.json")

#: Fields that change on every build and therefore mean no divergence.
VOLATILE_KEYS = {"built_at"}


def artifacts_dir() -> Path:
    """The artefact directory. Read afresh so that tests can substitute it."""
    return ARTIFACTS


def releases_dir() -> Path:
    return RELEASES


def _normalize(payload):
    if isinstance(payload, dict):
        return {
            key: _normalize(value)
            for key, value in payload.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    return payload


def readiness() -> list[str]:
    """The reasons a release must not be cut. An empty list means it may.

    A release fixes a state for ever, so it is checked more strictly than an
    ordinary pass. There are three checks, and each closes a case this very code
    demonstrated.

    First, the data has to be sound. The release used to call no validation at
    all, and nothing stopped it fixing a spoiled registry for ever.

    Second, the artefacts have to be built from the current data. The numbers of
    a release come from `data/` while the files are copied from
    `ui/public/data/`, and the two were never compared. The divergence was not
    theoretical: a snapshot claimed sixty-two technologies and held one.

    Third, every file the snapshot promises has to exist. A missing one was
    copied in silence, and the release promised in its own list a file it did
    not contain.
    """
    import build_artifacts
    import validate_data

    problems = [f"the data does not pass validation: {p}" for p in
                validate_data.check_registry()]

    missing = [name for name in SNAPSHOT_FILES
               if not (artifacts_dir() / name).exists()]
    if missing:
        problems.append(
            f"the artefacts are not built: {', '.join(missing)} missing; "
            "run `make artifacts`"
        )
        return problems

    with tempfile.TemporaryDirectory() as tmp:
        build_artifacts.build(out_dir=Path(tmp))
        for name in SNAPSHOT_FILES:
            fresh = Path(tmp) / name
            if not fresh.exists():
                continue
            expected = _normalize(json.loads(fresh.read_text(encoding="utf-8")))
            actual = _normalize(
                json.loads((artifacts_dir() / name).read_text(encoding="utf-8"))
            )
            if expected != actual:
                problems.append(
                    f"the artefact {name} was not built from the current data; "
                    "run `make artifacts` and commit the result"
                )
    return problems


def releases_index() -> list[dict]:
    """The snapshots released, the newest first."""
    path = releases_dir() / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("releases", [])


def is_complete(tag: str) -> bool:
    """Whether a snapshot was released in full.

    The release directory survived an interruption halfway through, and existence
    was exactly what got checked. An interrupted release stayed empty for ever: a
    second attempt saw the directory, reported that it already existed and left,
    while `publish` would have refused to overwrite it. Completeness is now asked
    of the content.
    """
    target = releases_dir() / tag
    if not (target / "release.json").exists():
        return False
    if any(not (target / name).exists() for name in SNAPSHOT_FILES):
        return False
    if not (releases_dir() / f"rag-world-{tag}.zip").exists():
        return False
    if not (releases_dir() / f"{tag}-deposit.json").exists():
        return False
    return any(item.get("tag") == tag for item in releases_index())


def build(tag: str | None = None, today: date | None = None) -> dict:
    """What a release is: a tag, a date, and what it fixed."""
    today = today or date.today()
    tag = tag or today.isoformat()
    technologies = store.load_technologies()
    return {
        "tag": tag,
        "released_at": today.isoformat(),
        "technologies": len(technologies),
        "evidence": len(store.load_evidence()),
        "with_level": sum(1 for t in technologies if store.latest_level(t.id)),
        "reviewed": sum(1 for t in technologies if t.configuration_reviewed),
        "files": list(SNAPSHOT_FILES),
    }


def publish(meta: dict) -> Path:
    """Write the snapshot. An existing release is never overwritten.

    The snapshot is assembled beside its destination and moved there in one
    stroke. An interruption halfway leaves a draft rather than half a release:
    the directory under the tag appears already complete. That matters more than
    usual here, because a release cannot be repeated — a link may already point
    at it.
    """
    target = releases_dir() / meta["tag"]
    if target.exists():
        raise FileExistsError(
            f"the release {meta['tag']} already exists: {target}. A release "
            "fixes a state for ever and must not be overwritten: a link to it "
            "may already have reached somebody else's work."
        )

    missing = [name for name in SNAPSHOT_FILES
               if not (artifacts_dir() / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"the snapshot is incomplete: {', '.join(missing)} missing. A "
            "release lists its own files, and promising one it lacks means "
            "handing out a link to nothing."
        )

    releases_dir().mkdir(parents=True, exist_ok=True)
    draft = Path(tempfile.mkdtemp(prefix=f".{meta['tag']}-", dir=releases_dir()))
    try:
        for name in SNAPSHOT_FILES:
            shutil.copy2(artifacts_dir() / name, draft / name)
        (draft / "release.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(draft, target)
    except BaseException:
        shutil.rmtree(draft, ignore_errors=True)
        raise

    index = [r for r in releases_index() if r["tag"] != meta["tag"]] + [meta]
    index.sort(key=lambda r: r["tag"], reverse=True)
    (releases_dir() / "index.json").write_text(
        json.dumps({"releases": index}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return target


def bundle(meta: dict) -> Path:
    """Build the release archive and the description for the external archive.

    The persistent identifier belongs to the data snapshot rather than to the
    source code: what is cited is the state of the registry, not the code that
    produced it. The external archive therefore takes the files directly, with
    no connection to version control.

    The description is written out ready beside it: filling it in by hand on
    every release means eventually mistyping a number, and the numbers here are
    the content.
    """
    target = releases_dir() / meta["tag"]
    archive = shutil.make_archive(
        str(releases_dir() / f"rag-world-{meta['tag']}"), "zip", root_dir=target
    )

    description = (
        f"A snapshot of the registry of Retrieval-Augmented Generation "
        f"technologies as of {meta['released_at']}. Technologies recorded: "
        f"{meta['technologies']}, evidence: {meta['evidence']}; a maturity level "
        f"is computed for {meta['with_level']}, and the configuration is read "
        f"out of the primary sources for {meta['reviewed']}. "
        "A level is derived by a deterministic rule from the collected "
        "evidence, with no language model taking part. The configuration of "
        "each record is read out of the method section of its primary source, "
        "and the justification of every value is stored with the data."
    )
    (releases_dir() / f"{meta['tag']}-deposit.json").write_text(
        json.dumps({
            "metadata": {
                "title": (
                    "RAG World: a registry of Retrieval-Augmented Generation "
                    f"technologies, release {meta['tag']}"
                ),
                "upload_type": "dataset",
                "description": description,
                "creators": [{"name": "Laputski, Alexander"}],
                "publication_date": meta["released_at"],
                "version": meta["tag"],
                "language": "eng",
                "keywords": [
                    "retrieval-augmented generation", "RAG", "feature model",
                    "technology readiness", "configuration space",
                ],
                "access_right": "open",
                "license": "cc-by-4.0",
            },
            "files": [Path(archive).name],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return Path(archive)


def run(*, dry_run: bool = False, today: date | None = None) -> int:
    meta = build(today=today)
    print(
        f"release {meta['tag']}: technologies {meta['technologies']}, "
        f"evidence {meta['evidence']}, with a level {meta['with_level']}, "
        f"reviewed {meta['reviewed']}"
    )

    # The checks run on a dry run as well: learning that a release must not be
    # cut is better done before the release than instead of it.
    problems = readiness()
    if problems:
        sys.stderr.write(f"a release must not be cut: {len(problems)} obstacles\n")
        for problem in problems:
            sys.stderr.write(f"  {problem}\n")
        return 1

    if dry_run:
        print("dry run: no obstacles, and nothing will be written")
        return 0

    if is_complete(meta["tag"]):
        print(f"the release {meta['tag']} already exists in full, no second one")
        return 0

    path = releases_dir() / meta["tag"]
    if path.exists():
        # The directory is there and the release is not: this state used to
        # report that it already existed and stayed that way for ever.
        sys.stderr.write(
            f"the release {meta['tag']} is not written in full: the directory "
            f"{path} exists while the snapshot, the archive, the description or "
            "the index entry does not. Remove the directory and release again, "
            "if nobody has cited this release yet.\n"
        )
        return 1

    print(f"the snapshot is written: {publish(meta)}")
    archive = bundle(meta)
    print(
        f"the package for the external archive: {archive.name}, description "
        f"{meta['tag']}-deposit.json"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show without writing")
    args = parser.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
