"""Машиночитаемый вход портала: указатель наборов, карта сайта, llms.txt.

Данные лежали в открытом каталоге и раньше, но узнать об их существовании
можно было только прочитав исходный код портала. Отсюда потребитель, которому
нужны сведения, разбирал страницы: получал худшие данные и ломался при первой
правке вёрстки.

Три файла закрывают это, и все три обязаны описывать то, что действительно
опубликовано. Указатель, обещающий набор, которого нет, хуже отсутствия
указателя: по нему напишут обращение, и оно откажет у потребителя, а не здесь.
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
DATA = PUBLIC / "data"

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads((DATA / "index.json").read_text(encoding="utf-8"))


def test_every_named_dataset_exists(index):
    """Указатель называет только то, что действительно лежит рядом."""
    missing = [
        entry["url"]
        for entry in index["datasets"]
        if not (DATA / entry["url"].rsplit("/", 1)[-1]).exists()
    ]
    assert not missing, (
        f"указатель обещает наборы, которых нет: {missing}. По такому "
        "указателю напишут обращение, и откажет оно у потребителя."
    )


def test_record_counts_match_the_files(index):
    """Число записей взято из файла, а не из намерения сборки."""
    wrong = []
    for entry in index["datasets"]:
        key = entry.get("records_at")
        if not key:
            continue
        name = entry["url"].rsplit("/", 1)[-1]
        payload = json.loads((DATA / name).read_text(encoding="utf-8"))
        actual = len(payload.get(key, []))
        if actual != entry["records"]:
            wrong.append(f"{name}: обещано {entry['records']}, лежит {actual}")
    assert not wrong, "указатель разошёлся с наборами: " + "; ".join(wrong)


def test_every_published_dataset_is_named(index):
    """Набор, оставшийся вне указателя, для потребителя не существует."""
    named = {entry["url"].rsplit("/", 1)[-1] for entry in index["datasets"]}
    published = {
        path.name for path in DATA.glob("*.json")
        if path.name != "index.json"
    }
    forgotten = published - named
    assert not forgotten, (
        f"наборы опубликованы, но в указателе не названы: {sorted(forgotten)}"
    )


def test_index_carries_what_an_integration_needs(index):
    """Подключение не должно требовать чтения кода портала."""
    for field in ("name", "site", "built_at", "license", "attribution",
                  "repository", "schema", "technologies", "technology_ids",
                  "datasets", "releases", "sitemap"):
        assert field in index, f"в указателе нет поля {field}"
    assert index["schema"]["dimensions"] == build_artifacts.SCHEMA_SIZE
    assert index["schema"]["rule_version"] == build_artifacts.RULE_VERSION
    assert len(index["schema"]["strata"]) == 7
    assert index["license"]["url"].startswith("https://creativecommons.org/")


def test_technology_ids_match_the_registry(index):
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    assert index["technology_ids"] == sorted(t["id"] for t in registry["technologies"])
    assert index["technologies"] == len(registry["technologies"])


def test_sitemap_covers_every_card_and_section():
    """Карточка, отсутствующая в карте сайта, не будет найдена поиском."""
    root = ET.fromstring((PUBLIC / "sitemap.xml").read_text(encoding="utf-8"))
    urls = {node.findtext(f"{SITEMAP_NS}loc") for node in root}
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))

    missing_cards = [
        tech["id"] for tech in registry["technologies"]
        if f"{build_artifacts.SITE}/tech/{tech['id']}" not in urls
    ]
    assert not missing_cards, f"карточек нет в карте сайта: {missing_cards}"

    missing_routes = [
        route for route in build_artifacts.STATIC_ROUTES
        if f"{build_artifacts.SITE}{route}" not in urls
    ]
    assert not missing_routes, f"разделов нет в карте сайта: {missing_routes}"


def test_robots_points_at_the_sitemap():
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert f"Sitemap: {build_artifacts.SITE}/sitemap.xml" in robots
    # Обходчику, которому нужны сведения, а не разметка, сказано куда идти.
    assert "/data/index.json" in robots


def test_llms_txt_sends_the_reader_to_the_data():
    """Соглашение llmstxt.org: имя, изложение, ссылки на данные."""
    text = (PUBLIC / "llms.txt").read_text(encoding="utf-8")
    assert text.startswith("# RAG World")
    assert "\n> " in text, "нет краткого изложения после заголовка"
    assert f"{build_artifacts.SITE}/data/index.json" in text
    assert "Do not scrape" in text, (
        "модели не сказано главное: страницы разбирать не нужно"
    )
    for name, _key, _description in build_artifacts.DATASETS:
        assert f"/data/{name}" in text, f"в llms.txt не назван набор {name}"


def test_head_of_the_page_declares_the_dataset():
    """Разметка schema.org: портал публикует набор данных, а не статью."""
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '"@type": "Dataset"' in html
    assert 'rel="canonical"' in html
    assert 'name="description"' in html
    assert 'property="og:title"' in html
    assert build_artifacts.LICENSE_URL in html
    # Язык разметки, отданной сервером, совпадает с языком портала.
    assert '<html lang="en">' in html
