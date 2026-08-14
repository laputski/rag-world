#!/usr/bin/env python3
"""Validate the registry: schema, references, admissible configurations.

Runs inside the update chain and in the build checks. A failure means a release
must not be published.

What is checked without a network:

* every record parses against the schema, and its identifier matches the file
  name and satisfies the naming convention;
* the dimension values exist in the schema, and the configuration is admissible
  under the constraints Φ;
* the strata of a record belong to A–G;
* evidence and level-journal entries refer to technologies that exist;
* every source has an address, and its check status agrees with its date.

Whether the addresses resolve requires a network and is enabled separately::

    python3 scripts/validate_data.py               # without a network
    python3 scripts/validate_data.py --check-links # asking the sources

The separation is deliberate: the checks must pass with every external source
unreachable, or the portal could not be built without a network.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dimensions_schema import ALL_VALUES, STRATA, validate  # noqa: E402
from services.registry import store  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9_]+$")
LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5", "L6"}


def _residual_vocabulary() -> dict[str, dict]:
    """The vocabulary of residual mechanisms: code to entry.

    It is read on every validation rather than once at import. The update pass
    edits the data and validates it within one run, so a vocabulary read at
    import time would describe the state before those edits.
    """
    path = store.DATA_DIR / "residual_vocabulary.json"
    if not path.exists():
        return {}
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in payload.get("mechanisms", [])}


def check_filenames() -> list[str]:
    """A record's file name matches the identifier inside it.

    A divergence does not look like a breakage and does not stop the registry
    being read: records load by walking the files, and the identifier comes from
    the content. The damage arrives with the first write back, and every update
    pass writes the registry when the link check updates the marks. Saving goes
    by identifier, so a second file appears while the old one stays: one record
    becomes two under one identifier.
    """
    import json

    problems: list[str] = []
    if not store.TECHNOLOGIES_DIR.exists():
        return problems
    for path in sorted(store.TECHNOLOGIES_DIR.glob("*.json")):
        try:
            declared = json.loads(path.read_text(encoding="utf-8")).get("id")
        except json.JSONDecodeError as exc:
            problems.append(f"technologies/{path.name}: the file does not parse: {exc}")
            continue
        if declared != path.stem:
            problems.append(
                f"technologies/{path.name}: the identifier inside the file "
                f"{declared!r} does not match the file name {path.stem!r}; "
                "the first write back would split the record in two"
            )
    return problems


def check_registry() -> list[str]:
    """The checks that need no network. Returns the list of problems."""
    # Parsing the files comes first, because it alone names the culprit. The
    # schema reads the registry whole and, on a spoiled file, reports what did
    # not fit but not which file it was in. The pass runs without a person, and
    # its failure has to be worked out from the log afterwards, where the file
    # name is indispensable.
    problems: list[str] = check_filenames()

    try:
        technologies = store.load_technologies()
    except Exception as exc:
        problems.append(f"the registry does not read against the schema: {exc}")
        return problems

    if not technologies:
        problems.append("the registry is empty: no records in data/technologies/")
        return problems

    vocabulary = _residual_vocabulary()
    known: set[str] = set()
    for tech in technologies:
        where = f"technologies/{tech.id}.json"

        if not ID_RE.match(tech.id):
            problems.append(
                f"{where}: the identifier {tech.id!r} breaks the convention "
                "(lower-case Latin letters, digits and underscores)"
            )
        if tech.id in known:
            problems.append(f"{where}: the identifier {tech.id!r} is repeated")
        known.add(tech.id)

        if not tech.name.strip():
            problems.append(f"{where}: the name is empty")

        for group in tech.groups:
            if group not in STRATA:
                problems.append(f"{where}: unknown stratum {group!r}")

        # An attack acts upon a RAG system rather than being one: it has no
        # index, no retrieval and no synthesis. The rule spares such a record an
        # inapplicability mark on every single dimension.
        if tech.kind in store.KINDS_WITHOUT_CONFIGURATION and tech.configuration:
            problems.append(
                f"{where}: the kind {tech.kind!r} occupies no place in the "
                f"configuration space, yet the record carries "
                f"{len(tech.configuration)} values"
            )

        for code, value in tech.configuration.items():
            if code not in ALL_VALUES:
                problems.append(f"{where}: unknown dimension {code!r}")
            elif value not in ALL_VALUES[code]:
                problems.append(
                    f"{where}: dimension {code} has the value {value!r}, "
                    f"which the schema does not contain"
                )
        if tech.configuration:
            for error in validate(tech.configuration):
                problems.append(f"{where}: the configuration is inadmissible: {error}")

        # A residual refers to the vocabulary by code. Free text is refused: one
        # and the same mechanism worded differently in two records will not come
        # together in the count, and the residual queue would show ten rare
        # mechanisms instead of one frequent one.
        for mechanism in tech.residual:
            if mechanism not in vocabulary:
                problems.append(
                    f"{where}: the residual {mechanism!r} is not in the vocabulary "
                    f"data/residual_vocabulary.json"
                )

        # A reviewed record must assert something: either values, or that the
        # dimensions do not apply to it. The second is no dodge: the
        # configuration space describes RAG systems, and the registry holds
        # objects of another kind too. An attack on a store is not a system: it
        # has no index, no retrieval and no synthesis, and dimension values would
        # assert things about what does not exist at all, not merely in one
        # stratum.
        if (
            tech.configuration_reviewed
            and not tech.configuration
            and not tech.configuration_inapplicable
            and tech.kind not in store.KINDS_WITHOUT_CONFIGURATION
        ):
            problems.append(
                f"{where}: the configuration is marked as reviewed, yet the "
                "record asserts neither values nor inapplicability"
            )

        both = set(tech.configuration_variable) & set(tech.configuration_inapplicable)
        if both:
            problems.append(
                f"{where}: the dimensions {sorted(both)} are marked both "
                "variable and inapplicable at once"
            )
        for code in tech.configuration_variable:
            if code not in ALL_VALUES:
                problems.append(
                    f"{where}: the variable dimension {code!r} is outside the schema"
                )
            elif code not in tech.configuration:
                problems.append(
                    f"{where}: dimension {code} is marked variable yet carries no "
                    "value; the value of the fullest branch is what gets written"
                )
        for code in tech.configuration_inapplicable:
            if code not in ALL_VALUES:
                problems.append(
                    f"{where}: the inapplicable dimension {code!r} is outside "
                    "the schema"
                )
            elif code in tech.configuration:
                # A value on an inapplicable dimension asserts something about
                # what does not exist.
                problems.append(
                    f"{where}: dimension {code} is marked inapplicable yet carries "
                    f"the value {tech.configuration[code]!r}"
                )

        for link in tech.links:
            if not link.url.strip():
                problems.append(f"{where}: a source without an address")
            # Both marks that speak of an inspection must carry a date: the one
            # saying it resolves and the one saying it is closed by rights.
            # Without a date there is no telling when the address was looked at,
            # and the mark asserts something open-ended.
            if link.status in ("verified", "guarded") and link.verified_at is None:
                problems.append(
                    f"{where}: the source {link.url} is marked as inspected "
                    f"({link.status}), yet no check date is given"
                )

    for item in store.load_evidence():
        if item.technology_id not in known:
            problems.append(
                f"evidence: an item refers to an unknown technology "
                f"{item.technology_id!r}"
            )
        if not item.source.strip():
            problems.append(
                f"evidence: the {item.type} item on {item.technology_id} "
                "has no source"
            )

    for entry in store.load_levels():
        if entry.technology_id not in known:
            problems.append(
                f"levels: an entry refers to an unknown technology "
                f"{entry.technology_id!r}"
            )
        if entry.level not in LEVELS:
            problems.append(
                f"levels: {entry.technology_id} has the inadmissible level {entry.level!r}"
            )
        if not 0.0 <= entry.confidence <= 1.0:
            problems.append(
                f"levels: the confidence {entry.confidence} on {entry.technology_id} "
                "lies outside [0, 1]"
            )

    for point in store.load_metrics():
        if point.technology_id not in known:
            problems.append(
                f"metrics: a measurement refers to an unknown technology "
                f"{point.technology_id!r}"
            )
        if not point.source.strip():
            problems.append(
                f"metrics: the {point.metric} measurement on {point.technology_id} "
                "has no source"
            )

    return problems


def check_links() -> list[str]:
    """Whether the source addresses resolve. Needs a network."""
    from services.collectors.transport import RequestsTransport

    transport = RequestsTransport()
    problems: list[str] = []
    seen: set[str] = set()
    for tech in store.load_technologies():
        for link in tech.links:
            if link.url in seen:
                continue
            seen.add(link.url)
            try:
                status, _ = transport.get(link.url)
            except Exception as exc:
                problems.append(f"{tech.id}: {link.url} is unreachable ({exc})")
                continue
            if status >= 400:
                problems.append(f"{tech.id}: {link.url} answers with {status}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-links", action="store_true",
        help="also check that the source addresses resolve (needs a network)",
    )
    args = parser.parse_args()

    problems = check_registry()
    if args.check_links:
        problems += check_links()

    if problems:
        sys.stderr.write(f"Data validation failed: {len(problems)} problems\n")
        for problem in problems:
            sys.stderr.write(f"  {problem}\n")
        return 1

    technologies = store.load_technologies()
    evidence = store.load_evidence()
    levels = store.load_levels()
    print(
        f"Data validation passed: technologies {len(technologies)}, "
        f"evidence {len(evidence)}, level journal entries {len(levels)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
