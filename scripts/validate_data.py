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
* every source has an address, and its check status agrees with its date;
* a record that claims to merge the results of several sources says on what
  source that claim rests;
* a hand-drawn architecture diagram agrees with its record and reads in both
  languages.

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

from core.dimensions_schema import ALL_VALUES, DIMENSIONS, STRATA, validate  # noqa: E402
from services.registry import store  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9_]+$")
LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5", "L6"}

#: The dimension of source fusion and the value that asserts no fusion at all.
#: They are named rather than written into the rule below, because the rule
#: reads as a sentence about fusion and not as a comparison of two strings.
FUSION_CODE = "C3"
FUSION_NONE = "none"

RERANK_CODE = "D1"
RERANK_NONE = "none"

#: Records whose reranking still holds the old default and awaits the owner's
#: decision. Four stood here on 2026-10-20 and all were decided on 2026-10-21.
#: The list may only shrink: an entry that gains a justification or another
#: value must leave it, which the check below demands.
RERANK_AWAITING_DECISION: frozenset[str] = frozenset()


def _justified_dimensions() -> set[tuple[str, str]]:
    """The pairs of record and dimension for which a justification is written.

    The justifications live beside the registry rather than inside a record, so
    a rule about their presence has to read their file itself. Whether a
    justification agrees with the value it explains is settled elsewhere, by the
    sweep in `scripts/build_review.py`; here only its presence is asked about.

    The file is read on every validation for the same reason the vocabulary is:
    the update pass edits the data and validates it within one run.
    """
    path = store.DATA_DIR / "parse_notes.jsonl"
    if not path.exists():
        return set()
    import json

    pairs: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        note = json.loads(line)
        if note.get("code"):
            pairs.add((note.get("technology_id", ""), note["code"]))
    return pairs


def _justified_residuals() -> set[tuple[str, str]]:
    """The pairs of record and residual mechanism for which a justification is written.

    The card of a diagram step takes the wording of a residual and what the
    system does from this justification; without one the reader would see a
    bare code.
    """
    path = store.DATA_DIR / "parse_notes.jsonl"
    if not path.exists():
        return set()
    import json

    pairs: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and (note := json.loads(line)).get("residual"):
            pairs.add((note.get("technology_id", ""), note["residual"]))
    return pairs


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


#: What a verdict on a residual mechanism may say. `declined` means the queue
#: was examined and the mechanism deliberately left out of the schema. There is
#: no `admitted`: a mechanism admitted into the schema leaves the vocabulary
#: altogether, because it is no longer a residual.
RESIDUAL_VERDICTS = ("declined",)


def check_residual_verdicts(vocabulary: dict[str, dict]) -> list[str]:
    """A verdict on a residual states a decision and its grounds, in both tongues.

    A verdict takes a mechanism out of candidacy for a dimension of the schema,
    which is the heaviest thing the queue can do to it. A verdict without
    grounds would do that silently, and a reader meeting a mechanism mentioned
    four times and not offered for admission would have no way of learning why.
    """
    problems: list[str] = []
    for code, entry in sorted(vocabulary.items()):
        verdict = entry.get("verdict")
        if verdict is None:
            continue
        where = f"residual_vocabulary.json: {code}"
        if not isinstance(verdict, dict):
            problems.append(f"{where}: the verdict is not an object")
            continue
        decision = verdict.get("decision")
        if decision not in RESIDUAL_VERDICTS:
            problems.append(
                f"{where}: the verdict says {decision!r}, and the admissible "
                f"decisions are {list(RESIDUAL_VERDICTS)}"
            )
        for field in ("reason", "reason_en"):
            if not str(verdict.get(field) or "").strip():
                problems.append(f"{where}: the verdict has no {field}")
        if not str(verdict.get("decided_at") or "").strip():
            problems.append(f"{where}: the verdict has no date")
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
    problems += check_residual_verdicts(vocabulary)
    # A spoiled file of justifications is reported rather than raised: the pass
    # runs unattended, and a traceback in its log names no file.
    try:
        justified = _justified_dimensions()
    except ValueError as exc:
        problems.append(f"data/parse_notes.jsonl does not read as JSON lines: {exc}")
        justified = set()
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

        # Any departure from "no fusion" asserts that the results of more than
        # one source are merged. That is a claim about the behaviour of a system,
        # and it can be checked only against the source: no other value of the
        # record implies it, and no collector observes it.
        #
        # The rule is narrow deliberately. Justifying every departure from the
        # base configuration is the eventual goal and is not reachable today,
        # seventy-one values standing without one. This dimension is singled out
        # because the harm was observed rather than imagined: of the two records
        # asserting a fusion that nobody had justified, one named an arithmetic
        # its own source contradicts, and the error had stood since the record
        # was first read.
        #
        # A justification does not make a value right. It makes an unchecked
        # value visible, which is the most a rule can do about a claim that only
        # a person reading the source can settle.
        fusion = tech.configuration.get(FUSION_CODE)
        if fusion not in (None, FUSION_NONE) and (tech.id, FUSION_CODE) not in justified:
            problems.append(
                f"{where}: {FUSION_CODE}={fusion!r} asserts that the results of "
                "several sources are merged, and no justification says which "
                "source that rests on"
            )

        # The same holds for reranking, and here the harm was observed at scale.
        # The first registry wrote the default of the schema into every record,
        # and that default was a joint encoder: forty-three of fifty-four records
        # claimed one. When the default became "no reranking", twenty-five such
        # claims survived as explicit values, and two independent blind readings
        # of their sources (2026-10-20) found no reranker in fourteen of them.
        # An inherited value looks exactly like a reading; a justification is what
        # tells them apart.
        rerank = tech.configuration.get(RERANK_CODE)
        awaiting = tech.id in RERANK_AWAITING_DECISION
        if rerank not in (None, RERANK_NONE) and (tech.id, RERANK_CODE) not in justified:
            if not awaiting:
                problems.append(
                    f"{where}: {RERANK_CODE}={rerank!r} asserts that the retrieved "
                    "candidates are reordered, and no justification says which "
                    "source that rests on"
                )
        elif awaiting:
            problems.append(
                f"{where}: the record no longer awaits a decision on {RERANK_CODE}; "
                "remove it from RERANK_AWAITING_DECISION"
            )

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

    problems += check_diagrams(technologies, vocabulary)
    return problems


#: Where the wording of the diagrams lives, one file per language.
WORDING_DIR = Path(__file__).resolve().parent.parent / "ui" / "src" / "i18n"

ARXIV_ID_RE = re.compile(r"\d{4}\.\d{4,5}")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def _same_source(url: str, links: list[str]) -> bool:
    """Whether a diagram is drawn from a source the record itself names.

    A preprint has several addresses (the abstract, the PDF, the HTML rendering
    of a given version), so two addresses of one preprint are matched by its
    identifier rather than letter by letter.
    """
    found = ARXIV_ID_RE.search(url)
    if found:
        return any(found.group(0) in link for link in links)
    return any(url.startswith(link) or link.startswith(url) for link in links)


def check_diagrams(
    technologies: list,
    vocabulary: dict[str, dict],
    wording_dir: Path | None = None,
) -> list[str]:
    """The hand-drawn architecture diagrams agree with the records they illustrate.

    A diagram is drawn by a person from the primary source, so nothing derives
    it and nothing keeps it current by itself. These checks are what keeps it
    from becoming a claim without a source or a picture of a reading since
    revised:

    * every step names a section of the source, and the source is one the
      record itself lists;
    * a step that carries a dimension carries the value the record holds, so a
      revised configuration breaks the build instead of leaving a stale picture;
    * no decision of the record disappears from the diagram unnoticed: a
      dimension departing from the base, or chosen at run time, stands on a step
      or is named among the omissions with a reason;
    * every step reads in both languages, and the English wording holds no
      Cyrillic;
    * a residual on a step has a justification, which the card of the step
      shows in place of the code.
    """
    import json

    problems: list[str] = []
    directory = store.DATA_DIR / "diagrams"
    if not directory.exists():
        return problems
    wording_dir = wording_dir or WORDING_DIR
    wording = {
        language: json.loads((wording_dir / language / "diagrams.json").read_text(encoding="utf-8"))
        for language in ("ru", "en")
    }
    by_id = {tech.id: tech for tech in technologies}
    defaults = {d.code: d.default for d in DIMENSIONS}
    explained = _justified_residuals()
    drawn: set[str] = set()

    for path in sorted(directory.glob("*.json")):
        where = f"diagrams/{path.name}"
        spec = json.loads(path.read_text(encoding="utf-8"))
        tech_id = spec.get("technology_id", "")
        drawn.add(tech_id)
        if path.stem != tech_id:
            problems.append(f"{where}: the file is named apart from the record {tech_id!r}")
        tech = by_id.get(tech_id)
        if tech is None:
            problems.append(f"{where}: no record {tech_id!r} in the registry")
            continue

        url = spec.get("source", {}).get("url", "")
        if not _same_source(url, [link.url for link in tech.links]):
            problems.append(f"{where}: the source {url!r} is not among the links of the record")

        sections = {s.get("key"): s for s in spec.get("sections", [])}
        for key, section in sections.items():
            if not section.get("title") or not section.get("anchor"):
                problems.append(f"{where}: section {key!r} lacks a title or an anchor")
            elif section["anchor"].startswith("#"):
                # The build joins the address and the anchor with a "#" of its
                # own; a second one yields "##section", which leads nowhere.
                problems.append(f"{where}: the anchor of section {key!r} starts with '#'")

        nodes = spec.get("nodes", {})
        placed = [node_id for row in spec.get("rows", []) for node_id in row]
        for node_id in sorted(set(placed) - set(nodes)):
            problems.append(f"{where}: the row holds an undefined step {node_id!r}")
        for node_id in sorted(set(nodes) - set(placed)):
            problems.append(f"{where}: step {node_id!r} stands in no row")
        for node_id in sorted({n for n in placed if placed.count(n) > 1}):
            problems.append(f"{where}: step {node_id!r} stands in more than one place")
        row_of = {
            node_id: r for r, row in enumerate(spec.get("rows", [])) for node_id in row
        }
        for source, target in spec.get("edges", []):
            if source not in nodes or target not in nodes:
                problems.append(f"{where}: the edge {source}→{target} names an undefined step")
            elif row_of.get(target) != (row_of.get(source, -2) + 1):
                problems.append(
                    f"{where}: the edge {source}→{target} must join a step to one in the next row"
                )

        for source, target in spec.get("loops", []):
            if source not in nodes or target not in nodes:
                problems.append(f"{where}: the loop {source}→{target} names an undefined step")
            elif placed.index(target) >= placed.index(source) or row_of[target] not in (
                row_of[source], row_of[source] - 1
            ):
                problems.append(
                    f"{where}: the loop {source}→{target} must return to an earlier step "
                    "of the same or the previous row"
                )
        for left, right in spec.get("breaks", []):
            row = spec.get("rows", [])[row_of[left]] if left in row_of else []
            if right not in row or row.index(right) != row.index(left) + 1:
                problems.append(
                    f"{where}: the break {left}|{right} must name neighbours of one row"
                )

        carried: set[str] = set()
        for node_id, node in nodes.items():
            if node.get("section") not in sections:
                problems.append(f"{where}: step {node_id!r} names no section of the source")
            for code, value in node.get("codes", {}).items():
                carried.add(code)
                if code not in ALL_VALUES:
                    problems.append(
                        f"{where}: step {node_id!r} carries an unknown dimension {code!r}"
                    )
                    continue
                if value not in ALL_VALUES[code]:
                    problems.append(
                        f"{where}: step {node_id!r} gives {code} the value {value!r}, "
                        "which the schema does not contain"
                    )
                held = tech.configuration.get(code)
                if code in tech.configuration_inapplicable:
                    problems.append(
                        f"{where}: step {node_id!r} carries {code}, which the record "
                        "marks inapplicable"
                    )
                elif held != value and code not in tech.configuration_variable:
                    problems.append(
                        f"{where}: step {node_id!r} says {code}={value!r}, while the "
                        f"record holds {held!r}"
                    )
            mechanism = node.get("residual")
            if mechanism and (mechanism not in tech.residual or mechanism not in vocabulary):
                problems.append(
                    f"{where}: step {node_id!r} names the residual {mechanism!r}, "
                    "which the record or the vocabulary lacks"
                )
            elif mechanism and (tech_id, mechanism) not in explained:
                problems.append(
                    f"{where}: step {node_id!r} names the residual {mechanism!r}, "
                    "which no justification explains; the card would show a bare code"
                )

        decisions = {
            code for code, value in tech.configuration.items() if value != defaults.get(code)
        } | set(tech.configuration_variable)
        omitted = set(spec.get("omitted", []))
        for code in sorted(decisions - carried - omitted):
            problems.append(
                f"{where}: the record decides {code}={tech.configuration.get(code)!r}, and "
                "the diagram neither shows it nor names it among the omissions"
            )
        for code in sorted(omitted - decisions):
            problems.append(f"{where}: {code} is omitted, yet the record makes no decision there")
        for code in sorted(omitted & carried):
            problems.append(f"{where}: {code} is both shown and omitted")

        for language in ("ru", "en"):
            texts = wording[language].get(tech_id, {})
            named = texts.get("nodes", {})
            for node_id in sorted(set(nodes) - set(named)):
                problems.append(f"{where}: step {node_id!r} has no {language} wording")
            for node_id in sorted(set(named) - set(nodes)):
                problems.append(
                    f"{where}: the {language} wording names a step {node_id!r} not drawn"
                )
            for node_id, fields in named.items():
                if not fields.get("title"):
                    problems.append(f"{where}: step {node_id!r} has no {language} title")
            for code in sorted(omitted):
                if not texts.get("omitted", {}).get(code):
                    problems.append(f"{where}: the omission of {code} has no {language} reason")
            # A line written in one language and not the other reaches one
            # reader and not the other, and a consumer of the data gets half a
            # step. The second line and the note are optional, but in pairs.
            other = wording["en" if language == "ru" else "ru"].get(tech_id, {}).get("nodes", {})
            for node_id, fields in named.items():
                for field in sorted(set(fields) - set(other.get(node_id, {}))):
                    problems.append(
                        f"{where}: step {node_id!r} has a {language} {field} without its twin"
                    )
            if language == "en":
                cyrillic = [
                    f"{node_id}.{field}"
                    for node_id, fields in named.items()
                    for field, text in fields.items()
                    if CYRILLIC_RE.search(text)
                ] + [
                    f"omitted.{code}"
                    for code, text in texts.get("omitted", {}).items()
                    if CYRILLIC_RE.search(text)
                ]
                if cyrillic:
                    problems.append(f"{where}: Cyrillic in the English wording: {cyrillic}")

    for language in ("ru", "en"):
        for tech_id in sorted(set(wording[language]) - drawn):
            problems.append(
                f"{language}/diagrams.json: wording for {tech_id!r}, which has no diagram"
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
