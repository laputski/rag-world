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
