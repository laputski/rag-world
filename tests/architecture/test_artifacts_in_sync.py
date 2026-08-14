"""The published artefacts must not diverge from the registry.

The artefacts are derived from `data/` and are versioned deliberately: the static
hosting builds the interface only and runs no Python, so without them the
published portal would be left with no data.

Versioning something derived has a price — it can go stale. This guard does not
let it: it rebuilds the artefacts into a temporary directory and compares them
with what is in the repository. A divergence means somebody edited the data and
forgot to run the build.

The build timestamp is ignored in the comparison: it changes on every run and
carries no content.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_artifacts import OUT_DIR, build  # noqa: E402

#: Fields that change on every build and are therefore excluded from comparison.
VOLATILE_KEYS = {"built_at"}

COMPARED = ["registry.json", "map.json", "changes.json", "stats.json"]


def _normalize(payload):
    """Strip the volatile fields at every level of the structure."""
    if isinstance(payload, dict):
        return {
            key: _normalize(value)
            for key, value in payload.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    return payload


def test_published_artifacts_match_registry(tmp_path):
    build(out_dir=tmp_path)

    stale: list[str] = []
    for name in COMPARED:
        published = OUT_DIR / name
        assert published.exists(), (
            f"the artefact {name} is missing from the repository; run "
            "`make artifacts`"
        )
        expected = _normalize(json.loads((tmp_path / name).read_text(encoding="utf-8")))
        actual = _normalize(json.loads(published.read_text(encoding="utf-8")))
        if expected != actual:
            stale.append(name)

    assert not stale, (
        "the published artefacts have diverged from the registry: "
        + ", ".join(stale)
        + "; run `make artifacts` and commit the result"
    )


# ─── Fields that hold nothing ────────────────────────────────────────────────
#
# A field empty across every record at once looks like data and is treated as
# data. That is how the spread field lived: the artefact carried it, the interface
# set the size of a point from it, and no record had a quantity behind it. Every
# point was the same size, and noticing that took looking at the map and asking
# why they all looked alike.
#
# An ordinary test does not catch this: a check that "no data means no zero" runs
# idle exactly when there is never any data. It is caught by a sweep across the
# whole artefact, so the check lives here, beside the one that looks at the real
# data rather than at invented data.

#: Fields legitimately empty across every record, with the reason.
ALLOWED_ALL_EMPTY = {
    # Empty while no record has been promoted or demoted: the field appears only
    # when a level changes.
}


def _all_empty_fields(items: list[dict]) -> list[str]:
    """The fields that are empty in every record of a dataset."""
    keys: set[str] = set()
    for item in items:
        keys |= set(item)
    empty = []
    for key in sorted(keys):
        values = [item.get(key) for item in items]
        if all(value is None or value == [] or value == {} for value in values):
            empty.append(key)
    return empty


def test_no_field_is_empty_for_every_record():
    """No field of an artefact is empty across every record at once."""
    offenders: dict[str, list[str]] = {}
    for name, path in (
        ("map.json", "points"),
        ("registry.json", "technologies"),
    ):
        payload = json.loads((OUT_DIR / name).read_text(encoding="utf-8"))
        items = payload[path] if isinstance(payload, dict) else payload
        dead = [
            key for key in _all_empty_fields(items)
            if key not in ALLOWED_ALL_EMPTY
        ]
        if dead:
            offenders[name] = dead

    assert not offenders, (
        f"fields empty across every record at once: {offenders}. Either nobody "
        "computes the quantity or the field is superfluous. Both look on the portal "
        "like data that is not there."
    )


def test_feed_is_published():
    """The chronicle feed is the only way to learn of a change without visiting."""
    feed = OUT_DIR / "feed.xml"
    assert feed.exists(), "the feed is missing; run `make artifacts`"
    text = feed.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml"), "the feed is not an XML document"
    assert "<channel>" in text


def test_residual_codes_are_resolved_to_wording():
    """The data stores a mechanism code and the reader is shown the wording.

    The split exists for the sake of translation: the English localisation
    translates the vocabulary rather than fifty-four registry records. But if the
    substitution breaks, a card shows the reader `synonymy_edges`, and that can
    only be noticed by eye.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    vocabulary = json.loads(
        (root / "data" / "residual_vocabulary.json").read_text(encoding="utf-8")
    )
    codes = {m["id"] for m in vocabulary["mechanisms"]}
    wording = {m["ru"] for m in vocabulary["mechanisms"]}

    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    seen = 0
    for row in published["technologies"]:
        for item in row.get("residual", []):
            seen += 1
            assert item not in codes, (
                f"a code reached the artefact instead of the wording: {item!r}"
            )
            assert item in wording, f"a wording outside the vocabulary: {item!r}"
    assert seen > 0, "no residual in the artefact at all: the check verifies nothing"


def test_marked_dimensions_survive_into_the_artifact():
    """The marks are useless if they do not reach the reader.

    They exist so that a value is not read as a claim it is not. Losing them at
    build time restores exactly the untruth the fields were introduced against.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    rows = {row["id"]: row for row in published["technologies"]}

    marked = [
        r for r in rows.values()
        if r.get("configuration_variable") or r.get("configuration_inapplicable")
    ]
    assert marked, "no marked record at all: the check verifies nothing"

    for row in marked:
        for code in row.get("configuration_inapplicable", []):
            assert code not in row["configuration"], (
                f"{row['id']}: the inapplicable dimension {code} carries a value"
            )
        for code in row.get("configuration_variable", []):
            assert code in row["configuration"], (
                f"{row['id']}: the variable dimension {code} carries no value"
            )


def test_rejected_names_do_not_return_to_the_registry():
    """A name once refused is not quietly created again.

    Half a year later the name surfaces again, nobody remembers why it was
    refused, and the work is repeated. The file of refusals answers the question,
    and this guard does not let the answer go stale unnoticed: if a record does
    enter the registry, it has to be removed from the file deliberately.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / "data" / "rejected.jsonl"
    if not path.exists():
        return

    rejected = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        assert row.get("reason", "").strip(), (
            f"{row.get('name')}: a refusal without a reason is useless"
        )
        if row.get("former_id"):
            rejected[row["former_id"]] = row["reason"]

    present = {p.stem for p in (root / "data" / "technologies").glob("*.json")}
    returned = sorted(rejected.keys() & present)
    assert not returned, (
        "refused records have returned to the registry: "
        + ", ".join(f"{i} ({rejected[i][:60]}…)" for i in returned)
    )


def test_parse_notes_agree_with_the_registry():
    """A justification that has drifted from the data is worse than none.

    It explains a value that is not there, and it does so convincingly: the reader
    sees coherent reasoning and does not think to check it.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import build_review

    notes = build_review.load_notes()
    if not notes:
        return
    problems = build_review.check(notes)
    assert not problems, (
        "the justifications have drifted from the registry:\n  "
        + "\n  ".join(problems)
    )


def test_parse_notes_say_both_what_and_why():
    """The split matters: one half is checked against the source, one against the
    schema.

    Merged into one phrase the thought reads as a claim about the technology,
    whereas half of it is a claim about how the schema describes that technology.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import build_review

    for note in build_review.load_notes():
        where = f"{note['technology_id']}.{note.get('code') or note.get('residual')}"
        assert note.get("did", "").strip(), f"{where}: it does not say what the system does"
        assert note.get("why", "").strip(), f"{where}: it does not say why the value follows"
        assert note.get("source", "").strip(), f"{where}: no source is given"


# ─── The reading justifications in two languages ─────────────────────────────


def test_every_justification_is_translated():
    """Every Russian field of a justification has an English one.

    The justifications were the only Russian text left on the English version of
    the cards. A partial translation is worse than none: a reader meeting a
    Russian paragraph in the middle of a page decides the portal is broken rather
    than that the translation is unfinished.

    The check runs over the data rather than over the artefact: a gap in the
    artefact would be lost at the first rebuild.
    """
    import json

    notes = [
        json.loads(line)
        for line in (ROOT / "data" / "parse_notes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert notes, "there are no reading justifications at all"

    missing = sorted(
        f"{n['technology_id']}.{n.get('code') or n.get('residual')}.{field}"
        for n in notes
        for field in ("did", "why", "instead", "question", "source")
        if n.get(field) and not n.get(field + "_en")
    )
    assert not missing, f"justifications with no translation: {missing[:12]}"


def test_translation_is_not_a_copy_of_the_original():
    """Russian text copied into an English field is not a translation."""
    import json
    import re

    cyrillic = re.compile(r"[а-яА-ЯёЁ]{4,}")
    notes = [
        json.loads(line)
        for line in (ROOT / "data" / "parse_notes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    untranslated = sorted(
        f"{n['technology_id']}.{n.get('code') or n.get('residual')}.{field}"
        for n in notes
        for field in ("did_en", "why_en", "instead_en", "question_en", "source_en")
        if n.get(field) and cyrillic.search(n[field])
    )
    assert not untranslated, f"Russian text remains in an English field: {untranslated[:12]}"
