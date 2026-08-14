"""The numbers in the scientific text must not diverge from the implementation.

The founding defect of this project was that the code, the data and the texts
said different things about one and the same subject. The article is especially
vulnerable: its numbers are typed by hand and go stale in silence. It happened
once already — the text reported a degree of independence of "about 0.97" while
the implementation returned 0.9984.

This test compares the claims of the article with what the code produces. It
deliberately checks little: only the quantities that are computed, and only where
a discrepancy misleads the reader.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.dimensions_schema import (  # noqa: E402
    DIMENSIONS,
    STRATA,
    dead_values,
    independence_degree,
)

ARTICLE = ROOT / "ui" / "src" / "generalizedData.ts"


def _article_text() -> str:
    assert ARTICLE.exists(), f"the text of the article is missing: {ARTICLE}"
    return ARTICLE.read_text(encoding="utf-8")


def test_independence_degree_matches_implementation():
    """The degree of independence in the text matches the computed one."""
    text = _article_text()
    computed = independence_degree()
    # In the Russian text the decimal separator is a comma.
    expected = f"{computed:.4f}".replace(".", ",")
    assert expected in text, (
        f"the article does not carry the current degree of independence "
        f"{expected}; recompute it and update the text"
    )
    # Stale values are looked for relative to the computed one rather than by a
    # written-in exception: a written-in one goes stale along with the number, and
    # the guard then starts calling the correct value stale. That happened once.
    stale = [
        found for found in re.findall(r"0,9\d{3}\b", text) if found != expected
    ]
    assert not stale, f"stale degrees of independence remain in the article: {stale}"


# The numerals up to thirty that appear in the text spelled out. The size of the
# schema changes rarely and deliberately, so the list is short: the point is that
# the guard should demand the article be updated rather than adapt to it.
SPELLED = {
    26: ("двадцати шести", "двадцать шесть", "26"),
    27: ("двадцати семи", "двадцать семь", "27"),
    28: ("двадцати восьми", "двадцать восемь", "28"),
    29: ("двадцати девяти", "двадцать девять", "29"),
    30: ("тридцати", "тридцать", "30"),
}


def _mentions_size_ru(text: str, form: str) -> bool:
    """A number beside the word for "dimension", in either order."""
    escaped = re.escape(form)
    return bool(
        re.search(rf"{escaped}\s+измерен\w*|измерен\w*\s+{escaped}", text)
    )


def test_schema_size_claim_matches_declaration():
    """The number of dimensions in the text matches the declared one.

    The number is not written in: the guard takes it from the schema. A written-in
    number goes stale with the next edit to the schema, and then a correct text
    fails — which is exactly what happened with the degree of independence.

    What is checked is not only that the correct number is present but that no
    stale one is. A guard satisfied by the first correct mention let a stale one
    through: the abstract spoke of twenty-eight dimensions while the description
    of the schema, two paragraphs down, still said twenty-six.
    """
    text = _article_text()
    size = len(DIMENSIONS)
    assert size in SPELLED, (
        f"the schema has {size} dimensions; add the spelling to SPELLED"
    )
    assert any(_mentions_size_ru(text, form) for form in SPELLED[size]), (
        f"the article lacks the current number of dimensions ({SPELLED[size][0]})"
    )
    stale = [
        form for value, forms in SPELLED.items() if value != size
        for form in forms if _mentions_size_ru(text, form)
    ]
    assert not stale, f"a stale number of dimensions remains in the article: {stale}"


#: The spelling of the number of dimensions in English. A translated abstract
#: goes stale apart from its original: while the guard watched only the Russian
#: text, the English one claimed twenty-six dimensions for half a year against
#: twenty-eight declared.
SPELLED_EN = {
    26: "twenty-six", 27: "twenty-seven", 28: "twenty-eight",
    29: "twenty-nine", 30: "thirty",
}


def test_english_abstract_states_the_same_schema_size():
    text = _article_text()
    size = len(DIMENSIONS)
    assert size in SPELLED_EN, (
        f"the schema has {size} dimensions; add the spelling to SPELLED_EN"
    )
    assert f"{SPELLED_EN[size]} dimensions" in text, (
        f"the English abstract lacks the current number of dimensions "
        f"({SPELLED_EN[size][0]})"
        f"({SPELLED_EN[size]})"
    )
    stale = [
        form for value, form in SPELLED_EN.items()
        if value != size and f"{form} dimensions" in text
    ]
    assert not stale, f"a stale number remains in the English abstract: {stale}"


def test_locale_strings_state_the_current_schema_size():
    """The number of dimensions is named in the interface labels too.

    The label of the Foundations section explained in both languages that "there
    are twenty-six dimensions" when there were twenty-eight. The guard did not
    look there, because it is not the article but a line of the localisation.
    """
    size = len(DIMENSIONS)
    locales = ROOT / "ui" / "src" / "i18n"

    ru = (locales / "ru.json").read_text(encoding="utf-8")
    stale_ru = [
        form for value, forms in SPELLED.items() if value != size
        for form in forms if _mentions_size_ru(ru, form)
    ]
    assert not stale_ru, f"ru.json names a stale number of dimensions: {stale_ru}"

    en = (locales / "en.json").read_text(encoding="utf-8")
    stale_en = [
        form for value, form in SPELLED_EN.items()
        if value != size and re.search(rf"{form}\s+dimensions?", en)
    ]
    assert not stale_en, f"en.json names a stale number of dimensions: {stale_en}"


#: The living documents where the number of dimensions is a claim about the
#: present state.
#:
#: The `research/` directory is deliberately excluded: it holds the plans written
#: before the rebuild, and editing the numbers there would turn an archive into a
#: forgery. It reads as history rather than as a description of the present.
DOCUMENTS_STATING_SCHEMA_SIZE = (
    "README.md",
    "governance/CONSTITUTION.md",
    "governance/DECISIONS.md",
    "specs/stages/STAGE-portal-rebuild.md",
    "specs/stages/STAGE-compare-and-inverse.md",
    "core/__init__.py",
    "core/configuration.py",
    "core/dimensions_schema.py",
)


def test_documents_state_the_current_schema_size():
    """The number of dimensions is the same in every living document.

    The schema grew to twenty-eight while fourteen places went on saying
    twenty-six: the front page of the description, the constitution, the decision
    log, the stage specifications and the description of the schema in its own
    file. Each of them reads as a claim about the present state, and each was
    wrong.
    """
    size = len(DIMENSIONS)
    stale: dict[str, list[str]] = {}
    for name in DOCUMENTS_STATING_SCHEMA_SIZE:
        text = (ROOT / name).read_text(encoding="utf-8")
        found = [
            form for value, forms in SPELLED.items() if value != size
            for form in forms if _mentions_size_ru(text, form)
        ]
        if found:
            stale[name] = found
    assert not stale, (
        f"documents name a stale number of dimensions: {stale}; the schema has "
        f"{size}"
    )


def test_strata_count_claim_matches_declaration():
    text = _article_text()
    assert len(STRATA) == 7
    assert "семи стратам" in text or "семь стратов" in text or "семи стратов" in text


def test_dead_values_claim_matches_implementation():
    """The claim that there are no dead values is checked against the code."""
    text = _article_text()
    claims_none = "Мёртвые значения отсутствуют" in text
    if claims_none:
        assert dead_values() == [], (
            "the article claims there are no dead values, "
            f"while the computation yields {dead_values()}"
        )


# ─── The references and the claim to novelty ─────────────────────────────────


def test_every_cited_number_has_a_reference():
    """A reference to a number absent from the list leads the reader nowhere.

    The failure is quiet: "[42]" stays in the text, the list ends at some smaller
    number, and noticing it takes proofreading. The check is cheap and is exactly
    the sort of thing a machine should do.
    """
    text = _article_text()
    declared = {int(n) for n in re.findall(r'label:\s*"\[(\d+)\]', text)}

    # The reference list itself is excluded line by line rather than cut off at
    # the word "refs": that word also appears in a type declaration, and cutting
    # there left six hundred characters of text without a single reference. The
    # check passed all the same — it compared an empty set with a full one.
    body = "\n".join(
        line for line in text.splitlines()
        if not re.match(r'\s*\{\s*label:\s*"\[\d+\]', line)
    )

    # A grouped reference "[2, 3]" is parsed whole: a pattern that took only the
    # first number would let a dangling second one through.
    cited: set[int] = set()
    for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", body):
        cited |= {int(n) for n in re.findall(r"\d+", group)}

    assert cited, "no reference found in the text: the pattern has drifted"
    orphans = sorted(cited - declared)
    assert not orphans, f"numbers cited with no entry in the list: {orphans}"


def test_novelty_claim_stays_narrow():
    """The claim stays within what was checked and does not return to an absolute.

    The former wording asserted that applying a feature model to RAG "has not been
    published". A search found adjacent work, and the claim was narrowed to what
    was actually checked. This guard does not let it roll back.
    """
    text = _article_text()
    assert "конфигурационному пространству не опубликовано" not in text, (
        "the absolute claim to novelty has returned"
    )
    assert "не удалось обнаружить формальной модели признаков" in text, (
        "the claim to novelty is not phrased as the result of a search"
    )


def test_prior_art_search_states_its_limits():
    """A claim of absence is worth exactly as much as its stated limits."""
    text = _article_text()
    for expected in ("Границы проверки", "Систематического обхода"):
        assert expected in text, f"the search section does not mention: {expected}"


def test_adjacent_variability_works_are_cited():
    """The adjacent work on variability management is cited by name.

    It exists, it applies the same apparatus to neighbouring objects, and saying
    nothing about it would inflate this project's contribution.
    """
    text = _article_text()
    for marker in ("3646548.3672581", "2501.00532", "2602.17697"):
        assert marker in text, f"an adjacent work is not cited: {marker}"


# ─── The size of the registry ────────────────────────────────────────────────
#
# The registry grows, and any number counted from it by hand goes stale. So it
# did: the conclusion claimed fifty-four records for half a year while the
# abstract of the same article spoke of sixty-two. A reader sees a portal
# arguing with itself.

#: The turns of phrase the article names the size of the registry with.
REGISTRY_SIZE_PATTERNS = (
    r"(\S+)\s+(?:запис\w+|технологи\w+|архитектур\w*)\s+(?:из\s+)?реестра",
    r"(\S+)\s+registry\s+(?:technolog\w*|entr\w*)",
)

#: Numerals spelled out. The list is closed and serves one purpose: to notice
#: that the size of the registry is written in words and to demand digits. The
#: figures themselves are computed, so the list does not go stale with the
#: registry — it is not a list of spellings of a particular number.
NUMERAL_RU = {
    "одной", "одна", "двух", "две", "трёх", "три", "четырёх", "четыре",
    "пяти", "пять", "шести", "шесть", "семи", "семь", "восьми", "восемь",
    "девяти", "девять", "десяти", "десять", "двадцати", "двадцать",
    "тридцати", "тридцать", "сорока", "сорок", "пятидесяти", "пятьдесят",
    "шестидесяти", "шестьдесят", "семидесяти", "семьдесят", "восьмидесяти",
    "восемьдесят", "девяноста", "девяносто", "ста", "сто",
}
NUMERAL_EN = re.compile(
    r"^(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"(?:twen|thir|for|fif|six|seven|eigh|nine)ty(?:-\w+)?|hundred)$",
    re.IGNORECASE,
)


def _registry_size_claims(text: str) -> list[tuple[str, str]]:
    """Pairs of numeral and whole phrase, for every claim of a size."""
    claims = []
    for pattern in REGISTRY_SIZE_PATTERNS:
        for found in re.finditer(pattern, text):
            claims.append((found.group(1).strip('"«»,;:'), found.group(0)))
    return claims


def test_registry_size_is_written_in_digits():
    """The size of the registry is written in digits, or nothing can check it.

    Spelled out, the number cannot be compared with the data, and it changes on
    every pass. The rule of "once a year and deliberately" that allows a list of
    spellings for the number of dimensions does not apply here.
    """
    spelled = [
        whole for word, whole in _registry_size_claims(_article_text())
        if word.lower() in NUMERAL_RU or NUMERAL_EN.match(word)
    ]
    assert not spelled, (
        f"the size of the registry is spelled out: {spelled}. It changes on every "
        "pass, and spelled out it cannot be checked against the data. Use digits."
    )


def test_registry_size_claims_match_the_data():
    """Every count of registry records in the text matches the registry."""
    from services.registry import store

    total = len(store.load_technologies())
    stated = [
        int(word) for word, _ in _registry_size_claims(_article_text())
        if word.isdigit()
    ]
    assert stated, "the article does not say how many records the schema was checked on"
    wrong = sorted(set(stated) - {total})
    assert not wrong, (
        f"the article states a registry size of {wrong} while the data holds {total}"
    )


def test_residual_share_claim_matches_the_registry():
    """The phrase "N records out of M" with a residual is checked against the registry."""
    from services.registry import store

    technologies = store.load_technologies()
    expected = (len([t for t in technologies if t.residual]), len(technologies))
    # The phrase occurs both as "5 records out of 62" and inside "for the
    # remaining N out of 65": the pattern takes both.
    stated = [
        (int(part), int(whole))
        for part, whole in re.findall(r"(\d+)\s+запис\w+ из (\d+)", _article_text())
    ]
    assert stated, "the article does not say how many records have a non-empty residual"
    wrong = sorted(set(stated) - {expected})
    assert not wrong, (
        f"the article states {wrong} while the registry has {expected[0]} records "
        f"with a non-empty residual out of {expected[1]}"
    )


def test_justification_count_matches_the_data():
    """The count of reading justifications comes from the journal, not from memory."""
    notes = ROOT / "data" / "parse_notes.jsonl"
    expected = len(
        [line for line in notes.read_text(encoding="utf-8").splitlines() if line.strip()]
    )
    stated = [int(n) for n in re.findall(r"обоснований (\d+)", _article_text())]
    assert stated, "the article does not say how many reading justifications there are"
    wrong = sorted(set(stated) - {expected})
    assert not wrong, (
        f"the article states {wrong} justifications while the journal holds {expected}"
    )


def test_coverage_claim_matches_the_registry():
    """The coverage figure in the article is computed rather than typed by hand.

    The article used to claim "96 per cent", derived from residuals that did not
    exist. The residuals are filled in now, the number has become checkable, and
    it must be checked.
    """
    from services.registry import store

    text = _article_text()
    technologies = store.load_technologies()
    expressed = [tech for tech in technologies if not tech.residual]
    share = round(100 * len(expressed) / len(technologies))

    # Russian agrees the word for "per cent" with the number before it. The guard
    # accepts every form, or it would fail on a correct number over grammar.
    tail = share % 10
    forms = [f"{share} процентов"]
    if tail == 1 and share % 100 != 11:
        forms.append(f"{share} процент")
    elif tail in (2, 3, 4) and share % 100 not in (12, 13, 14):
        forms.append(f"{share} процента")

    assert any(form in text for form in forms), (
        f"the article lacks the current coverage share ({forms[-1]}); "
        "it is computed from the residuals of the registry"
    )
    assert f"{share} percent" in text, (
        f"the English abstract lacks the current coverage share ({share} per cent)"
    )
