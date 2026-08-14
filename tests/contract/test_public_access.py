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
INDEX = ROOT / "ui" / "index.html"
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


# ─── Описания для поиска ─────────────────────────────────────────────────────

def test_descriptions_carry_no_counts():
    """Счёт в описании устаревает к следующему прогону.

    Описание страницы попадает в выдачу поиска и в предпросмотр ссылки, а там
    живёт неделями после того, как перестало быть верным. Строка «реестр из
    шестидесяти пяти технологий» была неверна уже на следующий прогон
    обнаружения, а исправить её у площадки, закешировавшей выдачу, нельзя.

    Запрещены цифры, а не числа вообще: «двадцать восемь измерений» устареет
    при первом же новом измерении ровно так же, поэтому счёт из описаний убран
    целиком, а проверка ловит его самый частый вид.
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
    # Разметка переносит длинные значения на свою строку, поэтому ищется и так.
    for match in re.finditer(
        r'(?:name|property)="(?:description|og:description)"\s*\n\s*content="([^"]*)"',
        html, re.S,
    ):
        if re.search(r"\d", match.group(1)):
            with_digits.append(match.group(1)[:70])
    assert not with_digits, f"счёт в описании страницы: {with_digits}"

    for language in ("ru", "en"):
        head = json.loads(
            (ROOT / "ui" / "src" / "i18n" / f"{language}.json").read_text(encoding="utf-8")
        )["head"]
        stale = [
            f"{language}.{page}"
            for page, value in head.items()
            if re.search(r"\d", value.get("description", ""))
        ]
        assert not stale, f"счёт в описании раздела: {stale}"


def test_keywords_are_declared_and_free_of_counts():
    """Слова-ключи на выдачу не влияют, но устаревать им тоже незачем."""
    import re

    html = INDEX.read_text(encoding="utf-8")
    match = re.search(r'name="keywords"\s*\n?\s*content="([^"]*)"', html, re.S)
    assert match, "слова-ключи не объявлены"
    words = [w.strip() for w in match.group(1).split(",") if w.strip()]
    assert len(words) >= 8, f"слов-ключей слишком мало: {len(words)}"
    assert not re.search(r"\d", match.group(1)), "счёт в словах-ключах"


# ─── Запись отдельным файлом ─────────────────────────────────────────────────

def test_every_record_is_published_on_its_own():
    """Карточка читает одну запись, а не весь реестр.

    Прежде страница технологии тянула восемьсот килобайт ради одной записи, и
    платила за это именно та страница, на которую чаще всего приходят по ссылке
    извне.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    folder = DATA / "tech"
    assert folder.is_dir(), "записи по одной не публикуются"

    published = {path.stem for path in folder.glob("*.json")}
    expected = {tech["id"] for tech in registry["technologies"]}
    assert published == expected, (
        f"лишние файлы: {sorted(published - expected)}; "
        f"недостающие: {sorted(expected - published)}"
    )


def test_a_single_record_matches_its_row_in_the_registry():
    """Два описания одной записи расходятся молча, если их не сверять.

    Карточка читает файл записи, а реестр читают страница списка и внешний
    потребитель. Разойдясь, они покажут разное об одной технологии, и заметить
    это можно будет только сравнив две страницы глазами.
    """
    registry = json.loads((DATA / "registry.json").read_text(encoding="utf-8"))
    rows = {tech["id"]: tech for tech in registry["technologies"]}
    mismatched: list[str] = []
    for path in sorted((DATA / "tech").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("technology") != rows.get(path.stem):
            mismatched.append(path.stem)
    assert not mismatched, f"файл записи разошёлся со строкой реестра: {mismatched}"


def test_a_single_record_is_far_smaller_than_the_registry():
    """Смысл разделения в размере: если файл не меньше, оно бессмысленно."""
    registry_size = (DATA / "registry.json").stat().st_size
    largest = max(path.stat().st_size for path in (DATA / "tech").glob("*.json"))
    assert largest * 10 < registry_size, (
        f"самая крупная запись {largest} байт против реестра {registry_size}: "
        "разделение перестало окупаться"
    )
