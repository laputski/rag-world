#!/usr/bin/env python3
"""The list of polled resources, generated from the collectors themselves.

There was no such list, and the only way to learn where the portal goes was to
read six modules. Written by hand it would have drifted from the code at the
first move of somebody else's catalogue, and a move has already happened: the
LangChain integrations went from `libs/community` to
`libs/langchain/langchain_classic`.

The file is therefore generated: addresses, paths and pauses are taken from the
collectors, and the only thing written by hand is what each resource is for.
Drift is impossible by construction, and a guard in
`tests/architecture/test_sources_in_sync.py` does not let the rebuild be
forgotten.

Usage::

    python3 scripts/build_sources.py            # rewrite docs/SOURCES.md
    python3 scripts/build_sources.py --check    # compare only, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.collectors import frameworks, transport  # noqa: E402
from services.collectors.arxiv import ARXIV_API  # noqa: E402
from services.collectors.curated import CURATED_LISTS  # noqa: E402
from services.collectors.github import GITHUB_API  # noqa: E402
from services.collectors.openalex import OPENALEX_API, OPENALEX_MAILTO_ENV  # noqa: E402
from services.collectors.paperswithcode import PWC_API, RAG_METHOD  # noqa: E402
from services.collectors.pypi import PYPI_API, STATS_API  # noqa: E402

OUT = ROOT / "docs" / "SOURCES.md"

#: What a resource is for: why the portal goes there and what it takes. The
#: prose cannot be derived from the code, so it lives here; the addresses, on
#: the contrary, come from the code alone.
PURPOSE = {
    ARXIV_API: (
        "Preprints",
        "Confirms that a preprint exists and compares its title with the one "
        "claimed. Yields the level L1.",
    ),
    OPENALEX_API: (
        "The open index of works",
        "The publication venue, whether it was peer-reviewed, the citation count "
        "and the citation velocity. Yields the level L2 by the scholarly route, "
        "and all the attention shown on the map.",
    ),
    GITHUB_API: (
        "Repositories",
        "The licence, the date of the last edit, whether releases exist. Yields "
        "the level L3. The same address serves the integration listings below.",
    ),
    PYPI_API: (
        "The package index",
        "That a package exists, and its version. It is asked only where the "
        "package name was written down by a person: guessing is inadmissible, "
        "because somebody else's package with a similar name would yield false "
        "evidence.",
    ),
    CURATED_LISTS[0].page: (
        "A curated topic list",
        "A second route of discovery, built on a different principle from the "
        "catalogue. The catalogue knows about a work what whoever uploaded it "
        "claimed, whereas inclusion in a list is the decision of a person who "
        "works in the subject. Only the identifiers of works are taken from the "
        "markup; what is known about them comes from the preprint archive, "
        "because a list is written by hand and its wording cannot be trusted.",
    ),
    PWC_API: (
        "The works-and-code catalogue",
        "The publication venue from a second source: while it came from the open "
        "index alone, an error there was covered by nothing. The same catalogue "
        f"gives a feed of works under the method tag `{RAG_METHOD}` for "
        "discovering new ones. It is run by the community after "
        "paperswithcode.com closed.",
    ),
    STATS_API: (
        "Package downloads",
        "The number of downloads in a month. Together with presence in a "
        "framework it yields the level L4.",
    ),
}


def render() -> str:
    lines = [
        "<!-- GENERATED from services/collectors/ by "
        "`python3 scripts/build_sources.py`. Do not edit by hand: an edit "
        "would be lost. -->",
        "",
        "# The resources polled",
        "",
        "These are the only places the portal goes. The list is generated from "
        "the code of the collectors, so it cannot drift from it.",
        "",
        "No key and no account is required anywhere. A hosting token is used "
        "when one is present, and only for the sake of a higher rate limit.",
        "",
        "## Entry points",
        "",
        "| Resource | Address | What is taken |",
        "| --- | --- | --- |",
    ]
    for url, (name, purpose) in PURPOSE.items():
        lines.append(f"| {name} | `{url}` | {purpose} |")

    lines += [
        "",
        "## Integration folders",
        "",
        "Directory listings are read rather than code search: a technology is "
        "present in a framework when a folder of its own exists. The paths "
        "change along with the layout of somebody else's repository, which "
        "makes this the most brittle part of the list.",
        "",
        "| Framework | Repository | Folders |",
        "| --- | --- | --- |",
    ]
    for catalog in frameworks.CATALOGS:
        paths = ", ".join(f"`{p}`" for p in catalog.paths)
        lines.append(f"| {catalog.name} | `{catalog.repo}` | {paths} |")

    lines += [
        "",
        "## Politeness",
        "",
        "The pause between two requests to one host. The values come from what "
        "the resources ask for, not from convenience.",
        "",
        "| Host | Pause, s |",
        "| --- | --- |",
    ]
    for host, delay in sorted(transport.HOST_DELAYS.items()):
        lines.append(f"| `{host}` | {delay} |")
    lines += [
        f"| any other | {transport.DEFAULT_DELAY} |",
        "",
        f"The portal introduces itself as `{transport.DEFAULT_USER_AGENT}`. "
        f"The open index of works keeps a separate request pool for those who "
        f"give a contact address: it is taken from the environment variable "
        f"`{OPENALEX_MAILTO_ENV}`, and without it a pass runs slower and risks "
        f"a refusal on rate.",
        "",
        f"Retries after a refusal on rate: {transport.RETRIES_ON_RATE_LIMIT}.",
        "",
        "## What the portal does not do by itself",
        "",
        "It does not create records. Discovery asks the catalogue under the "
        "method tag and appends what it finds to the candidate queue, and the "
        "verdict on each is a person's: a rule telling a new architecture from "
        "an application of an existing one errs, and the price of the error is "
        "a registry record about something that does not exist. The queue is "
        "shown on the Gaps page.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare only, and fail on a divergence")
    args = parser.parse_args()

    expected = render()
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            sys.stderr.write(
                f"{OUT.relative_to(ROOT)} has drifted from the collector code; "
                "run `python3 scripts/build_sources.py`\n"
            )
            return 1
        print("the list of resources matches the code")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(expected, encoding="utf-8")
    print(f"the list of resources is written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
