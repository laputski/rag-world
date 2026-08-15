"""The list of resources must not diverge from the collector code.

The list is generated from the collectors' own constants, so it cannot state an
untruth. It can, however, be left unrebuilt after somebody else's catalogue
moves, and then the document calmly asserts yesterday's arrangement. A move has
happened already: the LangChain integrations left `libs/community` for
`libs/langchain/langchain_classic`.

The same device as with the dimension schema for the interface: what is generated
is compared against its generator rather than checked for plausibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_sources  # noqa: E402


def test_sources_file_exists():
    assert build_sources.OUT.exists(), (
        "the list of resources is missing; run "
        "`python3 scripts/build_sources.py`"
    )


def test_sources_file_matches_the_collectors():
    actual = build_sources.OUT.read_text(encoding="utf-8")
    assert actual == build_sources.render(), (
        "the list of resources has diverged from the collector code; run "
        "`python3 scripts/build_sources.py` and do not edit the file by hand"
    )


def test_every_polled_address_is_listed():
    """An address the code polls has to be in the list.

    A new collector is easy to write and easy to forget to describe. The portal
    then goes where the documents say it does not, and the only way to learn that
    is to read the code — exactly the state the list exists to end.
    """
    listed = build_sources.render()
    missing = [url for url in build_sources.PURPOSE if url not in listed]
    assert not missing, f"an address is missing from the list: {missing}"

    # The other side: the list describes only what exists.
    import re

    # Every collector module is walked rather than a list of names: such a list
    # would have to be extended with every new collector, and that is exactly what
    # would be forgotten.
    declared = set()
    for path in sorted((ROOT / "services" / "collectors").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        declared |= set(re.findall(r'^[A-Z_]+ *= *"(https?://[^"]+)"', text, re.M))

    undocumented = sorted(
        url for url in declared
        if url not in build_sources.PURPOSE and url not in listed
    )
    assert not undocumented, (
        f"the collectors go to addresses absent from the list: {undocumented}. "
        "Add the purpose to PURPOSE and rebuild the list."
    )
