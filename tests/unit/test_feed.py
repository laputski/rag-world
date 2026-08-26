"""The feed has to be subscribable, not merely present.

A feed that exists and cannot be subscribed to is worse than none: it looks like
the problem is solved. Both feeds were generated for months while carrying no
dates and no links, so a reader who subscribed saw twenty issues stamped with
the moment they subscribed and had no way to reach the evidence under any of
them.

What is checked here is the part a reader's software depends on and a person
never sees: that a date parses as the format the standard names, that every item
leads somewhere, and that the channel states its own address.
"""

from __future__ import annotations

import sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_artifacts  # noqa: E402

ATOM = "{http://www.w3.org/2005/Atom}"

ISSUES = [
    {"issued_at": "2026-08-17", "text": "Русский текст", "text_en": "English text"},
    {"issued_at": "2026-08-14", "text": "Второй", "text_en": "Second"},
]

CHANGES = [
    {
        "technology_id": "hipporag",
        "name": "HippoRAG",
        "level_before": "L0",
        "level_after": "L4",
        "changed_at": "2026-08-10",
        "evidence": [{"type": "publication", "source": "https://example.org/p"}],
    }
]


@pytest.fixture
def feed(tmp_path):
    path = tmp_path / "feed.xml"
    build_artifacts._write_feed(path, CHANGES, "2026-08-17", ISSUES, "en")
    return path


@pytest.fixture
def channel(feed):
    return ElementTree.parse(feed).getroot().find("channel")


class TestDatesParse:
    """A date a reader cannot parse is a date the reader replaces with now."""

    def test_every_item_carries_a_publication_date(self, channel):
        items = channel.findall("item")
        assert items, "the feed came out empty"
        for item in items:
            assert item.findtext("pubDate"), f"no pubDate on {item.findtext('title')!r}"

    def test_item_dates_are_rfc822(self, channel):
        for item in channel.findall("item"):
            # Raises if the format is wrong, which is the whole assertion: this
            # is the same call a reader makes.
            parsedate_to_datetime(item.findtext("pubDate"))

    def test_the_build_date_is_rfc822(self, channel):
        parsedate_to_datetime(channel.findtext("lastBuildDate"))

    def test_a_date_keeps_the_day_it_was_given(self, channel):
        dates = {parsedate_to_datetime(i.findtext("pubDate")).date().isoformat()
                 for i in channel.findall("item")}
        assert {"2026-08-17", "2026-08-14", "2026-08-10"} == dates


class TestItemsLeadSomewhere:
    """The feed exists to bring a reader back to the evidence."""

    def test_every_item_has_a_link(self, channel):
        for item in channel.findall("item"):
            assert item.findtext("link"), f"no link on {item.findtext('title')!r}"

    def test_an_issue_links_to_the_digest_page(self, channel):
        issue = channel.findall("item")[0]
        assert issue.findtext("link").endswith("/digest")

    def test_a_level_change_links_to_that_record(self, channel):
        change = [i for i in channel.findall("item")
                  if "HippoRAG" in (i.findtext("title") or "")][0]
        assert change.findtext("link").endswith("/tech/hipporag")


class TestTheChannelDescribesItself:
    def test_the_feed_states_its_own_address(self, channel):
        link = channel.find(f"{ATOM}link")
        assert link is not None, "no atom:link rel=self"
        assert link.get("rel") == "self"
        assert link.get("href").endswith("/data/feed.xml")

    def test_the_russian_feed_names_the_russian_file(self, tmp_path):
        path = tmp_path / "feed.ru.xml"
        build_artifacts._write_feed(path, CHANGES, "2026-08-17", ISSUES, "ru")
        channel = ElementTree.parse(path).getroot().find("channel")
        assert channel.find(f"{ATOM}link").get("href").endswith("/data/feed.ru.xml")
        assert channel.findtext("language") == "ru"

    def test_each_language_carries_its_own_prose(self, tmp_path):
        ru = tmp_path / "feed.ru.xml"
        build_artifacts._write_feed(ru, CHANGES, "2026-08-17", ISSUES, "ru")
        russian = ElementTree.parse(ru).getroot().find("channel")
        assert "Русский текст" in russian.findall("item")[0].findtext("description")


class TestTheFeedStaysWellFormed:
    def test_prose_with_markup_in_it_does_not_break_the_xml(self, tmp_path):
        path = tmp_path / "feed.xml"
        build_artifacts._write_feed(
            path,
            [dict(CHANGES[0], name="A & B <script>")],
            "2026-08-17",
            [dict(ISSUES[0], text_en="5 > 3 & rising")],
            "en",
        )
        channel = ElementTree.parse(path).getroot().find("channel")
        titles = " ".join(i.findtext("title") or "" for i in channel.findall("item"))
        assert "A & B <script>" in titles
