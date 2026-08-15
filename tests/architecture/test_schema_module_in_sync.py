"""The generated interface schema must not diverge from the declaration.

The dimension schema is declared once, in `core/dimensions_schema.py`. The
interface needs it too, and its module is generated from that same declaration.
This test does not let the two drift apart: if the module was edited by hand or
the rebuild was forgotten after a change to the schema, it fails.

Two descriptions of one thing was the founding defect of this project; repeating
it in a new form is not an option.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_artifacts import SCHEMA_MODULE, render_schema_module  # noqa: E402


def test_generated_schema_module_matches_declaration():
    assert SCHEMA_MODULE.exists(), (
        "the schema module for the interface is missing; run `make artifacts`"
    )
    actual = SCHEMA_MODULE.read_text(encoding="utf-8")
    expected = render_schema_module()
    assert actual == expected, (
        "the interface schema has diverged from the declaration; run "
        "`make artifacts` and do not edit the generated module by hand"
    )


def test_locale_files_have_no_broken_characters():
    """A replacement character in a translation is the trace of a broken write.

    The failure is quiet: the line displays almost correctly, and noticing the
    lost letter takes proofreading. It happened once already.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for lang in ("ru", "en"):
        path = root / "ui" / "src" / "i18n" / f"{lang}.json"
        text = path.read_text(encoding="utf-8")
        assert "�" not in text, f"{lang}.json: corrupted characters in the translation"
        json.loads(text)  # the file has to stay parsable


#: The suffixes of the plural forms. Grammar sets the forms, and languages differ:
#: Russian needs `_one`, `_few` and `_many`, English needs `_one` and `_other`.
#: Comparing such keys directly would declare one language's grammar an error of
#: translation.
PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")

#: The forms a language requires. A missing one shows the reader the key instead
#: of the message on exactly the numbers that form covers.
REQUIRED_FORMS = {"ru": ("one", "few", "many"), "en": ("one", "other")}


def _locale_keys(root, language: str) -> set[str]:
    import json

    def flat(node: object, prefix: str = "") -> set[str]:
        if isinstance(node, dict):
            out: set[str] = set()
            for key, value in node.items():
                out |= flat(value, f"{prefix}.{key}")
            return out
        return {prefix}

    path = root / "ui" / "src" / "i18n" / f"{language}.json"
    return flat(json.loads(path.read_text(encoding="utf-8")))


def _stem(key: str) -> str:
    for form in PLURAL_FORMS:
        if key.endswith(f"_{form}"):
            return key[: -len(form) - 1]
    return key


def test_locales_declare_the_same_keys():
    """A key added in one language and forgotten in the other shows the key."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    ru = {_stem(key) for key in _locale_keys(root, "ru")}
    en = {_stem(key) for key in _locale_keys(root, "en")}
    assert ru == en, (
        f"only in Russian: {sorted(ru - en)}; only in English: {sorted(en - ru)}"
    )


def test_counted_messages_declare_every_form_the_language_needs():
    """A counted message without the right form breaks on certain numbers.

    In Russian "7 changes" and "2 changes" take different forms, and a message
    without the `_few` form shows the reader the key itself on the numbers from
    two to four. Looking at a page with seven changes will never reveal it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    problems: list[str] = []
    for language, required in REQUIRED_FORMS.items():
        keys = _locale_keys(root, language)
        stems = {_stem(key) for key in keys if _stem(key) != key}
        for stem in sorted(stems):
            missing = [form for form in required if f"{stem}_{form}" not in keys]
            if missing:
                problems.append(f"{language}{stem}: missing the forms {missing}")
    assert not problems, "counted messages are incomplete: " + "; ".join(problems)


#: Keys where a dash separates a label from its expansion rather than standing in
#: for a verb: "L0 — a hypothesis" is a glossary entry, not a sentence.
DASH_AS_LABEL = ("level.", "levelCondition.")


def test_dash_does_not_stand_in_for_a_verb():
    """In Russian texts for the reader, the relation is named by a word.

    A dash hides the relation between parts of a phrase: the reader has to work
    out for themselves whether it is a list, a cause or a definition. The portal
    explains difficult things to people seeing them for the first time, and it
    must not make them guess.

    This is a rule about the Russian text. The English is left as it is: there a
    dash is an ordinary mark of relation, and forbidding it would make the prose
    unnatural.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    def walk(node: object, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key)
        elif isinstance(node, str) and "—" in node:
            if not path.startswith(DASH_AS_LABEL):
                offenders.append(f"{path}: {node[:70]}")

    for name in ("ru.json", "ru/tech.json"):
        walk(json.loads((root / "ui" / "src" / "i18n" / name).read_text(encoding="utf-8")))

    assert not offenders, (
        "a dash stands in for a verb in a text for the reader:\n  "
        + "\n  ".join(offenders)
        + "\nPut a verb or a preposition there."
    )


def test_card_prose_is_translated_field_for_field():
    """A partial translation is worse than none.

    A reader of the English version meeting a Russian paragraph in the middle of a
    page decides the portal is broken rather than that the translation is
    unfinished. The failure has to be visible to the developer at build time and
    not to the reader on the page.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    ru = json.loads((root / "ui" / "src" / "i18n" / "ru" / "tech.json").read_text(encoding="utf-8"))
    en_path = root / "ui" / "src" / "i18n" / "en" / "tech.json"
    assert en_path.exists(), "there is no English prose at all"
    en = json.loads(en_path.read_text(encoding="utf-8"))

    missing_records = sorted(set(ru) - set(en))
    assert not missing_records, f"records with no English prose: {missing_records}"

    missing_fields = sorted(
        f"{key}.{field}" for key in ru for field in ru[key] if field not in en.get(key, {})
    )
    assert not missing_fields, f"fields with no translation: {missing_fields}"

    # And the converse: English text with no Russian original means a typo in the
    # key, and on the Russian version it disappears in silence.
    orphans = sorted(set(en) - set(ru))
    assert not orphans, f"English prose with no Russian original: {orphans}"


def test_translated_prose_is_not_a_copy_of_the_original():
    """Russian text copied into the English file is not a translation.

    It passes the completeness check while staying Russian. Telling one from the
    other is cheapest by alphabet.
    """
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    en = json.loads(
        (root / "ui" / "src" / "i18n" / "en" / "tech.json").read_text(encoding="utf-8")
    )
    cyrillic = re.compile(r"[а-яА-ЯёЁ]{4,}")
    untranslated = sorted(
        f"{key}.{field}" for key, block in en.items() for field, text in block.items()
        if cyrillic.search(text)
    )
    assert not untranslated, (
        f"Russian text remains in the English prose: {untranslated[:12]}"
    )
