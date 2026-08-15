"""The published data is localised: Russian text has an English twin.

The portal is bilingual and its artefacts were bilingual by halves. Some carried
the translation beside the original (`why` and `why_en`), some stayed Russian
only, and telling one from the other took looking. For a consumer reading the
data without the portal that meant a registry half-written in a language they do
not read.

The check walks every published file and demands: if a string carries Cyrillic, a
field of the same name with an `_en` suffix has to lie beside it. That convention
was chosen because it was already used in the justifications and in the residual
vocabulary; introducing a second one would mean two ways of saying the same
thing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ui" / "public" / "data"

CYRILLIC = re.compile("[а-яА-ЯёЁ]")

#: The files published for an outside consumer.
PUBLISHED = ("registry.json", "map.json", "changes.json", "stats.json",
             "residuals.json", "candidates.json", "digest.json", "index.json")

#: Fields where Cyrillic is legitimate with no twin.
#:
#: A technology named in Cyrillic would be an error of data rather than of
#: translation, so there are no exceptions by name here. The one concession
#: concerns a field whose content is Russian text by design: the note on the
#: residual vocabulary itself is stored in both languages as separate entries.
EXEMPT_PATHS: tuple[str, ...] = ()


def _walk(node: object, path: str, out: list[tuple[str, str, object]]) -> None:
    """Collect triples of path, key and parent for every Cyrillic string."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and CYRILLIC.search(value):
                out.append((f"{path}.{key}", key, node))
            else:
                _walk(value, f"{path}.{key}", out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, f"{path}[]", out)


@pytest.mark.parametrize("name", PUBLISHED)
def test_russian_text_has_an_english_twin(name):
    path = DATA / name
    if not path.exists():
        pytest.skip(f"{name} is not built")
    found: list[tuple[str, str, object]] = []
    _walk(json.loads(path.read_text(encoding="utf-8")), "", found)

    missing = []
    for where, key, parent in found:
        if where in EXEMPT_PATHS:
            continue
        # Cyrillic in a field declared English does not mean a missing twin but an
        # untranslated field. Demanding a twin for a twin makes no sense.
        if key.endswith("_en"):
            missing.append(f"{where} (declared English yet written in Russian)")
            continue
        twin = f"{key}_en"
        value = parent.get(twin) if isinstance(parent, dict) else None
        if not (isinstance(value, str) and value.strip()):
            missing.append(f"{where} (no {twin})")
    # The same field repeats across every record; naming it once is enough.
    unique = sorted({item.split(" (")[0] for item in missing})
    assert not missing, (
        f"{name}: Russian text with no English twin in the fields {unique}. A "
        "consumer of the data would receive a registry half in a language they do "
        "not read."
    )


def test_registry_carries_descriptions_in_both_languages():
    """A record's description belongs in the published data, not only on the page.

    The prose lived in the interface resources and never reached the artefacts at
    all: the registry, once published, consisted of codes and levels without a
    single sentence saying what a technology was.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    without: list[str] = []
    for tech in registry["technologies"]:
        described = tech.get("description") and tech.get("description_en")
        rubric = all(
            tech.get(field) and tech.get(f"{field}_en")
            for field in ("problem", "barriers", "solutions")
        )
        if not (tech.get("summary") and tech.get("summary_en")):
            without.append(f"{tech['id']}: no short summary")
        elif not described and not rubric:
            without.append(f"{tech['id']}: no full description")
    assert not without, "records published with no description: " + "; ".join(without)


def test_feed_is_published_in_both_languages():
    """A feed carries one language by construction, so there are two feeds."""
    for name, language in (("feed.xml", "en"), ("feed.ru.xml", "ru")):
        path = DATA / name
        assert path.exists(), f"the feed {name} is missing"
        text = path.read_text(encoding="utf-8")
        assert f"<language>{language}</language>" in text, (
            f"{name}: the language of the feed is undeclared or wrong"
        )
    english = (DATA / "feed.xml").read_text(encoding="utf-8")
    assert not CYRILLIC.search(english), (
        "the English feed contains Russian text"
    )


def test_index_names_both_feeds():
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    feeds = index.get("feeds")
    assert isinstance(feeds, dict), "the index does not name the feeds by language"
    assert set(feeds) == {"en", "ru"}, f"feeds in the index: {sorted(feeds)}"
