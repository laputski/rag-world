"""The real registry data passes its own validation.

The data validation existed before this, but it ran only through `make validate`
and as a separate step of continuous integration. Every test that touched it
substituted a temporary directory for the data: they checked the **rule** rather
than that the rule applies.

Hence the gap that once caught us out. An edit to a registry record kept `make
test` entirely green, because no test read the real data, and the violation
surfaced after the push, on somebody else's machine, in continuous integration.
The developer saw green meanwhile and had every reason to think the work was
finished.

The check needs no network: it covers the schema, referential integrity, the
provenance of numbers, and the consistency of the inspection marks. Whether the
addresses resolve is checked separately, on a schedule, because it depends on
other people's services.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data  # noqa: E402


def test_registry_passes_its_own_validation():
    problems = validate_data.check_registry()
    assert not problems, (
        "the registry data does not pass its own validation:\n  "
        + "\n  ".join(problems)
    )


def test_every_file_is_named_after_the_record_inside():
    """Separate, because a divergence here splits a record on the first write."""
    assert validate_data.check_filenames() == []


def test_validation_needs_no_network():
    """The validation has to work offline, or the run depends on other people.

    Whether the addresses resolve is a separate flag and a separate schedule: a
    publisher refusing must not paint the run red.
    """
    import services.collectors.transport as transport

    def refuse(*args, **kwargs):  # pragma: no cover — a call would mean a failure
        raise AssertionError("the data validation reached the network")

    original = transport.RequestsTransport.get
    transport.RequestsTransport.get = refuse
    try:
        validate_data.check_registry()
    finally:
        transport.RequestsTransport.get = original
