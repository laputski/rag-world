"""A smoke check of the deployed portal.

Kept apart from the main suite and outside it: it needs a network and checks the
result of a deployment rather than the code. Mixing the two is not an option — a
test that fails because of somebody else's network stops being read, and the rest
of the suite stops being read along with it.

To run::

    make smoke

What is checked is what breaks at deployment and nowhere else: the address
rewrite rule, the presence of the data files, the absence of requests to external
sources, and the agreement of what is published with what is in the repository.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

requests = pytest.importorskip("requests")

pytestmark = pytest.mark.network

#: The address of the deployed portal. The same one appears in render.yaml and in
#: the transport's introduction: the portal names itself by its own name when it
#: reaches other platforms. The platform also answers at its own address
#: (rag-world.onrender.com), but what is checked is what a reader sees.
BASE_URL = "https://ragworld.org"

HEADERS = {"User-Agent": "rag-world/0.2 (smoke check)"}
TIMEOUT = 30


@pytest.fixture(scope="module")
def index_html() -> str:
    resp = requests.get(BASE_URL + "/", headers=HEADERS, timeout=TIMEOUT)
    assert resp.status_code == 200
    return resp.text


def get(path: str):
    return requests.get(BASE_URL + path, headers=HEADERS, timeout=TIMEOUT)


# ─── The sections are reachable ──────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/", "/registry", "/changes", "/digest", "/article", "/about"])
def test_sections_answer(path):
    assert get(path).status_code == 200, path


def test_direct_link_to_a_card_opens(index_html):
    """A direct address for a card is a precondition of being citable.

    Without the rewrite rule the static hosting would answer "not found", and a
    link to a record from somebody else's work would lead into nothing.
    """
    resp = get("/tech/pathrag")
    assert resp.status_code == 200
    assert "<div id=\"root\">" in resp.text or "<title>" in resp.text


def test_unknown_address_gets_a_human_answer():
    """The rewrite rule serves index.html for any address.

    So a typo reaches the application, and the reader has to receive an
    intelligible answer rather than the router's debug screen addressing a
    developer. It is checked against the built page: the text itself is inserted in
    the browser, so it is enough here that the address was served and the shell
    returned.
    """
    resp = get("/no-such-address")
    assert resp.status_code == 200
    assert "Unexpected Application Error" not in resp.text


# ─── The data ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "registry.json", "map.json", "changes.json", "stats.json", "digest.json", "feed.xml",
])
def test_data_files_are_published(name):
    resp = get(f"/data/{name}")
    assert resp.status_code == 200, name
    assert resp.content, name


def test_published_data_matches_the_repository():
    """What is deployed is what is in the repository.

    A divergence means the deployment lagged behind or did not happen. The portal
    looks sound meanwhile: it shows data, only yesterday's.
    """
    live = get("/data/registry.json").json()
    local = json.loads(
        (ROOT / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    assert live["count"] == local["count"], (
        f"the platform has {live['count']} records, the repository {local['count']}"
    )
    assert live["built_at"] == local["built_at"], (
        f"built on the platform {live['built_at']}, in the repository "
        f"{local['built_at']}"
    )


def test_assets_are_served_not_rewritten(index_html):
    """Assets have to be served as themselves rather than as the portal shell.

    The rewrite rule catches any unknown address, so checking the status code means
    nothing: a 200 comes back for a file that does not exist. What has to be
    checked is the content type.
    """
    assets = re.findall(r"/assets/[A-Za-z0-9._-]+\.(?:js|css)", index_html)
    assert assets, "the built page carries no links to assets"
    for path in assets[:2]:
        resp = get(path)
        assert resp.status_code == 200, path
        assert "text/html" not in resp.headers.get("Content-Type", ""), (
            f"{path} was served as the portal shell instead of the file"
        )


# ─── Self-sufficiency ────────────────────────────────────────────────────────


def test_page_asks_no_external_host(index_html):
    """The portal must not depend on other platforms while rendering.

    The fonts and styles are built in deliberately: reaching an external one makes
    the portal hostage to its availability and reports the reader to a third
    party.
    """
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', index_html)
    allowed = (BASE_URL,)
    stray = [u for u in external if not u.startswith(allowed)]
    assert not stray, f"the page reaches outward: {stray[:5]}"
