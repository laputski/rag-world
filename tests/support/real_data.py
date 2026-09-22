"""What the test suite may read and never write: the real data.

The list lives here rather than in the suite's configuration because two
readers need it. The suite fails when a test has written into these paths; the
mutation run, which owns the tree while it runs, puts them back after every
mutant and reports the mutant apart from those a test caught.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The real data and everything derived from it that is versioned.
GUARDED = (
    "data",
    "docs",
    "ui/public",
    "ui/src/schema.generated.ts",
    "ui/src/rule.generated.ts",
)


def snapshot(root: Path = ROOT) -> dict[Path, bytes]:
    """The bytes of every guarded file under `root`."""
    files: dict[Path, bytes] = {}
    for name in GUARDED:
        path = root / name
        if path.is_file():
            files[path] = path.read_bytes()
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    files[item] = item.read_bytes()
    return files


def changed_between(before: dict[Path, bytes], after: dict[Path, bytes]) -> list[Path]:
    """The files written, created or deleted between two snapshots."""
    return sorted(
        path for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )


def restore(before: dict[Path, bytes], changed: list[Path]) -> None:
    """Put the changed files back as the first snapshot had them."""
    for path in changed:
        if path in before:
            path.write_bytes(before[path])
        elif path.exists():
            path.unlink()
