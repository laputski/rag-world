"""The machine-readable entrance: the index, the sitemap and llms.txt.

The data sat in an open directory before this too, and the only way to learn of
it was to read the source. Whoever needed the information parsed the pages, which
gives a worse result and breaks at the first edit to the layout.

Three files close that, and all three have to agree with what is actually
published. An index promising a dataset that does not exist is worse than no
index at all: somebody writes a request from it, and the request fails.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import build_artifacts  # noqa: E402

PUBLIC = ROOT / "ui" / "public"
INDEX = ROOT / "ui" / "index.html"
DATA = PUBLIC / "data"

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads((DATA / "index.json").read_text(encoding="utf-8"))


def test_every_named_dataset_exists(index):
    """The index names only what exists."""
    missing = [
        entry["url"]
        for entry in index["datasets"]
        if not (DATA / entry["url"].rsplit("/", 1)[-1]).exists()
    ]
    assert not missing, (
        f"the index promises datasets that are not published: {missing}. Somebody "
        "will write a request from the index, and the request will fail."
    )


def test_record_counts_match_the_files(index):
    """The record count comes from the file rather than from the build state."""
    wrong = []
    for entry in index["datasets"]:
        key = entry.get("records_at")
        if not key:
            continue
        name = entry["url"].rsplit("/", 1)[-1]
        payload = json.loads((DATA / name).read_text(encoding="utf-8"))
        actual = len(payload.get(key, []))
        if actual != entry["records"]:
            wrong.append(f"{name}: {entry['records']} promised, {actual} present")
    assert not wrong, "the index has diverged from the datasets: " + "; ".join(wrong)


def test_every_published_dataset_is_named(index):
    """A dataset left out of the index might as well not be published."""
    named = {entry["url"].rsplit("/", 1)[-1] for entry in index["datasets"]}
    published = {
        path.name for path in DATA.glob("*.json")
        if path.name != "index.json"
    }
    forgotten = published - named
    assert not forgotten, (
        f"datasets are published but absent from the index: {forgotten}"
    )


def test_index_carries_what_an_integration_needs(index):
    """Connecting to the data must require reading no code."""
    for field in ("name", "site", "built_at", "license", "attribution",
                  "repository", "schema", "technologies", "technology_ids",
                  "datasets", "releases", "sitemap"):
        assert field in index, f"the index has no field {field!r}"
    assert index["schema"]["dimensions"] == build_artifacts.SCHEMA_SIZE
    assert index["schema"]["rule_version"] == build_artifacts.RULE_VERSION
    assert len(index["schema"]["strata"]) == 7
    assert index["license"]["url"].startswith("https://creativecommons.org/")


def test_technology_ids_match_the_registry(index):
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    assert index["technology_ids"] == sorted(t["id"] for t in registry["technologies"])
    assert index["technologies"] == len(registry["technologies"])


def test_sitemap_covers_every_card_and_section():
    """A card missing from the sitemap is invisible to search."""
    root = ET.fromstring((PUBLIC / "sitemap.xml").read_text(encoding="utf-8"))
    urls = {node.findtext(f"{SITEMAP_NS}loc") for node in root}
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))

    missing_cards = [
        tech["id"] for tech in registry["technologies"]
        if f"{build_artifacts.SITE}/tech/{tech['id']}" not in urls
    ]
    assert not missing_cards, f"cards missing from the sitemap: {missing_cards[:5]}"

    missing_routes = [
        route for route in build_artifacts.STATIC_ROUTES
        if f"{build_artifacts.SITE}{route}" not in urls
    ]
    assert not missing_routes, f"sections missing from the sitemap: {missing_routes}"


def test_robots_points_at_the_sitemap():
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert f"Sitemap: {build_artifacts.SITE}/sitemap.xml" in robots
    # A crawler that wants the information should be sent to the data.
    assert "/data/index.json" in robots


def test_llms_txt_sends_the_reader_to_the_data():
    """The llmstxt.org convention: a name, a summary, links to the data."""
    text = (PUBLIC / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# RAG World")
    assert "\n> " in text, "there is no short summary"
    assert f"{build_artifacts.SITE}/data/index.json" in text
    assert "Do not scrape" in text, (
        "the model is not told the main thing: the pages need not be parsed"
    )
    for name, _key, _description in build_artifacts.DATASETS:
        assert f"/data/{name}" in text, f"llms.txt does not name {name}"


def test_head_of_the_page_declares_the_dataset():
    """schema.org markup: what the portal publishes is a dataset."""
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '"@type": "Dataset"' in html
    assert 'rel="canonical"' in html
    assert 'name="description"' in html
    assert 'property="og:title"' in html
    assert build_artifacts.LICENSE_URL in html
    # The language of the served markup matches the default language.
    assert '<html lang="en">' in html


# ─── The descriptions for search ─────────────────────────────────────────────

def test_descriptions_carry_no_counts():
    """A count in a description goes stale by the next pass.

    A page description reaches the search results and lives there for weeks after
    the count has changed. "A registry of sixty-five technologies" was wrong
    within a week of discovery running, and correcting it at the platform is not
    possible.

    Digits are forbidden rather than numbers as such: a written-out count goes
    stale at the first new record just as surely, and the check catches the
    simplest form.
    """
    import re

    html = INDEX.read_text(encoding="utf-8")
    with_digits: list[str] = []
    for match in re.finditer(
        r'(?:name|property)="(?:description|og:description)"[^>]*?content="([^"]*)"',
        html, re.S,
    ):
        if re.search(r"\d", match.group(1)):
            with_digits.append(match.group(1)[:70])
    # The markup wraps long attribute values across lines.
    for match in re.finditer(
        r'(?:name|property)="(?:description|og:description)"\s*\n\s*content="([^"]*)"',
        html, re.S,
    ):
        if re.search(r"\d", match.group(1)):
            with_digits.append(match.group(1)[:70])
    assert not with_digits, f"a count in a page description: {with_digits}"

    for language in ("ru", "en"):
        head = json.loads(
            (ROOT / "ui" / "src" / "i18n" / f"{language}.json").read_text(encoding="utf-8")
        )["head"]
        stale = [
            f"{language}.{page}"
            for page, value in head.items()
            if re.search(r"\d", value.get("description", ""))
        ]
        assert not stale, f"a count in a section description: {stale}"


def test_keywords_are_declared_and_free_of_counts():
    """Keywords affect no ranking, but a stale count in them is still wrong."""
    import re

    html = INDEX.read_text(encoding="utf-8")
    match = re.search(r'name="keywords"\s*\n?\s*content="([^"]*)"', html, re.S)
    assert match, "no keywords are declared"
    words = [w.strip() for w in match.group(1).split(",") if w.strip()]
    assert len(words) >= 8, f"too few keywords: {words}"
    assert not re.search(r"\d", match.group(1)), "a count among the keywords"


# ─── One record as its own file ──────────────────────────────────────────────

def test_every_record_is_published_on_its_own():
    """A card reads one record rather than the whole registry.

    A technology page used to pull eight hundred kilobytes, and the page paying
    for it was exactly the one people arrive at from an outside link.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    folder = DATA / "tech"
    assert folder.is_dir(), "records are not published one by one"

    published = {path.stem for path in folder.glob("*.json")}
    expected = {tech["id"] for tech in registry["technologies"]}
    assert published == expected, (
        f"extra files: {sorted(published - expected)}; "
        f"missing: {sorted(expected - published)}"
    )


def test_a_single_record_matches_its_row_in_the_registry():
    """Two descriptions of one record drift apart.

    A card reads the record file while the registry is read by a consumer. Once
    they diverge they show different things, and noticing it takes comparing two
    files by hand.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    rows = {tech["id"]: tech for tech in registry["technologies"]}
    mismatched: list[str] = []
    for path in sorted((DATA / "tech").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("technology") != rows.get(path.stem):
            mismatched.append(path.stem)
    assert not mismatched, f"a record file has diverged from the registry: {mismatched[:5]}"


def test_a_single_record_is_far_smaller_than_the_registry():
    """The split exists for size: if a record grows, the split stops paying."""
    registry_size = (DATA / "registry.json").stat().st_size
    largest = max(path.stat().st_size for path in (DATA / "tech").glob("*.json"))
    assert largest * 10 < registry_size, (
        f"the largest record is {largest} bytes: the split has stopped paying"
    )
