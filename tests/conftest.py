"""The root conftest for pytest.

The suite splits into a fast part and a networked one. The fast part runs
entirely without a network and without external stores: the checks have to pass
when every source is unreachable, or the portal could not be built without an
internet connection.

The smoke checks of the deployed portal are marked `network` and stay out of the
main suite: a test that fails because of somebody else's network stops being
read, and the rest of the suite stops being read along with it.
"""

import pytest


# The marker for integration tests against live backends. CI does not run them.
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: needs live backends (Qdrant/OpenSearch/LLM); "
        "not run in CI by default.",
    )


# ─── What a test may not touch ───────────────────────────────────────────────

import os  # noqa: E402
from pathlib import Path  # noqa: E402

from tests.support.real_data import ROOT, changed_between, snapshot  # noqa: E402

#: Where the guarded paths are looked for. Only the test of this guard moves
#: it, to a directory of its own, so that proving the guard fires writes
#: nothing real.
GUARD_ROOT = Path(os.environ.get("RAG_WORLD_GUARD_ROOT", ROOT))

REAL_DATA_WRITTEN = "the test run wrote into the real data:"
NETWORK_REACHED = "the test reached for the network:"


@pytest.fixture(scope="session", autouse=True)
def real_data_stays_untouched():
    """The suite fails when any test has written into the real data.

    A module that fixes a path at import follows no substitution of the data
    directory made later, and a test believing itself isolated writes the
    original. That happened on 2026-09-22: the end-to-end test of the weekly
    pass rescored the real candidate queue under a mutant of the fitness rule,
    and every mutant after it was killed by the artefact comparison, which the
    changed queue had broken. The same mechanism had rewritten the queue once
    before.

    The files are reported, not restored. A person may be editing the data
    while the suite runs, and putting the old bytes back would destroy that
    work; the mutation run, which owns the tree while it runs, restores them
    itself (see `tests/support/real_data.py`).
    """
    before = snapshot(GUARD_ROOT)
    yield
    changed = changed_between(before, snapshot(GUARD_ROOT))
    if changed:
        names = ", ".join(str(path.relative_to(GUARD_ROOT)) for path in changed)
        pytest.fail(f"{REAL_DATA_WRITTEN} {names}", pytrace=False)


@pytest.fixture(autouse=True)
def no_network(request, monkeypatch):
    """A test outside `tests/smoke` that reaches for the network fails.

    The end-to-end tests of the weekly pass sent about a hundred real requests
    per run for weeks: the link check built a real transport because no test
    handed it one. Their outcome depended on somebody else's servers, which is
    the thing this suite is built not to depend on.

    The attempt is refused as a dead network would refuse it, and the test
    fails afterwards rather than at the call. The code under test catches
    network failures on purpose, so an exception alone would be swallowed and
    the test would pass without anyone learning that it had tried.
    """
    if request.node.get_closest_marker("network"):
        yield
        return
    import requests

    attempts: list[str] = []

    def refuse(self, method, url, *args, **kwargs):
        attempts.append(f"{method} {url}")
        raise requests.ConnectionError(f"the test suite has no network: {url}")

    monkeypatch.setattr(requests.Session, "request", refuse)
    yield
    if attempts:
        pytest.fail(
            f"{NETWORK_REACHED} {len(attempts)} requests, the first {attempts[0]}",
            pytrace=False,
        )
