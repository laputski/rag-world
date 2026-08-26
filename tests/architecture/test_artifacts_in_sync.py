"""The published artefacts must not diverge from the registry.

The artefacts are derived from `data/` and are versioned deliberately: the static
hosting builds the interface only and runs no Python, so without them the
published portal would be left with no data.

Versioning something derived has a price — it can go stale. This guard does not
let it: it rebuilds the artefacts into a temporary directory and compares them
with what is in the repository.

A divergence has two causes, and the message names whichever one fits. Usually
somebody edited the data and did not rebuild. But two quantities are computed
against the clock rather than against the data: the staleness mark, and the
confidence of a level, which falls as the evidence behind it passes its period of
relevance. Once the data is old enough, a rebuild differs from what is published
with nobody having touched anything, and what that asks for is a collection pass,
not a build. Told only the first cause, whoever meets this would look for an edit
that was never made.

What is compared is everything the build writes, and the list of what that is
comes from the build itself rather than from a list of names kept here. A list
is a thing to forget: the sitemap and the pointer for language models were
missing from this one for as long as they had existed, and it cost ten days of a
sitemap telling crawlers the site had not changed since the fourteenth while the
data ran to the twenty-fourth. An artefact added tomorrow is compared from the
day it is first written.

The walk goes one way, from what was rebuilt to what is published. The published
directory holds things this build does not produce and must not judge: the
icons, the redirects, and the releases, which are snapshots fixed for ever by a
different script. Walking the other way would demand a list of exceptions, and
that is the same list under another name.

The build date is stripped from the JSON all the same. It is derived from the
freshest piece of data rather than from the clock, so it moves only when the
data moves, and stripping it costs nothing.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.maturity import FRESHNESS_DAYS  # noqa: E402
from scripts.build_artifacts import OUT_DIR, STALE_AFTER, build  # noqa: E402

#: Fields that change on every build and are therefore excluded from comparison.
VOLATILE_KEYS = {"built_at"}


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


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory):
    """The artefacts as today's data produces them, in the layout the host serves.

    The tree has the shape of `ui/public`: the data in a directory of its own,
    the sitemap and llms.txt beside it. That shape is not decoration. The build
    writes those two to the parent of the directory it is given, so a bare
    temporary directory would scatter them into whatever happened to contain it,
    where a comparison would never think to look.

    The build runs once for the whole module: it reads the registry entire, and
    doing that twice to compare two halves of one result would be waste.
    """
    root = tmp_path_factory.mktemp("public")
    build(out_dir=root / "data")
    return root


def _calendar_note(age: int) -> str:
    """What to add to the message when the calendar alone could explain it.

    The two ages are taken from the code that computes the quantities rather
    than written down again here: the staleness mark from the period the build
    calls stale, the confidence from the shortest period any evidence stays
    current for. Restating either would make this message go quietly wrong the
    day one of them changed.

    Nothing is said while the data is young: a divergence then really is a
    forgotten build, and a paragraph about the calendar would only send the
    reader looking in the wrong place.
    """
    reasons = [
        (STALE_AFTER.days, "the staleness mark turns over"),
        (min(FRESHNESS_DAYS.values()), "the confidence of a level starts to fall"),
    ]
    reached = [f"{why} at {days} days" for days, why in reasons if age >= days]
    if not reached:
        return ""
    return (
        f". The freshest data is {age} days old, and this may be the calendar rather than "
        f"a forgotten build: {', and '.join(reached)}, with nobody having edited anything. "
        "If that is what happened, what it asks for is a collection pass, `make collect`"
    )


def _differs(fresh: Path, published: Path) -> bool:
    """Whether two artefacts differ in anything that carries meaning.

    JSON is compared as structure, so that the build date and the order a
    dictionary happens to be written in do not count as a divergence. Everything
    else is compared byte for byte: the feeds, the sitemap and llms.txt carry
    only dates derived from the data, so a rebuild over unchanged data
    reproduces them exactly, and anything less strict would let a difference
    through unexamined.
    """
    if fresh.suffix == ".json":
        return (
            _normalize(json.loads(fresh.read_text(encoding="utf-8")))
            != _normalize(json.loads(published.read_text(encoding="utf-8")))
        )
    return fresh.read_text(encoding="utf-8") != published.read_text(encoding="utf-8")


def test_published_artifacts_match_registry(rebuilt):
    published_root = OUT_DIR.parent

    missing: list[str] = []
    stale: list[str] = []
    for fresh in sorted(path for path in rebuilt.rglob("*") if path.is_file()):
        name = str(fresh.relative_to(rebuilt))
        published = published_root / fresh.relative_to(rebuilt)
        if not published.exists():
            missing.append(name)
        elif _differs(fresh, published):
            stale.append(name)

    # A file the build writes and the repository does not hold is never the
    # calendar: no amount of waiting deletes a file.
    assert not missing, (
        "the build writes artefacts that are not in the repository: "
        + ", ".join(missing)
        + "; run `make artifacts` and commit the result"
    )

    built_at = json.loads((rebuilt / "data" / "registry.json").read_text(encoding="utf-8"))
    age = (date.today() - date.fromisoformat(built_at["built_at"])).days
    assert not stale, (
        "the published artefacts have diverged from the registry: "
        + ", ".join(stale)
        + "; run `make artifacts` and commit the result"
        + _calendar_note(age)
    )


def test_no_card_outlives_its_record(rebuilt):
    """A card is published per record, and the walk above cannot see a leftover.

    The comparison goes from the rebuilt tree to the published one, so a file
    the build no longer produces is invisible to it. For the cards that matters:
    the build deletes the card of a record that has left the registry precisely
    because a permanent address must not go on answering, and a leftover would
    keep answering with a record nothing else knows about.
    """
    produced = {path.name for path in (rebuilt / "data" / "tech").glob("*.json")}
    published = {path.name for path in (OUT_DIR / "tech").glob("*.json")}
    orphans = sorted(published - produced)
    assert not orphans, (
        "cards published for records that are no longer in the registry: "
        + ", ".join(orphans)
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
