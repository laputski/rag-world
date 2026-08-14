#!/usr/bin/env python3
"""Build the artefacts the portal reads.

The portal is static: it never reaches the registry while serving, it reads
files built in advance. That yields the property the whole arrangement exists
for, which is that a source going down ages the data instead of breaking the
portal.

What is built::

    public/data/registry.json   the registry entire; filtering happens in the browser
    public/data/map.json        the points of the maturity map
    public/data/changes.json    the chronicle of changes, each linked to its evidence
    public/data/stats.json      the summary: distribution, coverage, freshness
    public/data/digest.json     digest issues, the newest first
    public/data/residuals.json  the residual queue: what the schema does not express
    public/data/candidates.json the candidate queue: what is not in the registry yet
    public/data/feed.xml        the feed: issues and level changes

No number reaches an artefact without provenance. Attention and spread come from
the measurement series, and where there is no series the field stays empty and
the view must say that there is no data rather than show a zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dimensions_schema import DIMENSIONS, SCHEMA_SIZE, STRATA  # noqa: E402
from core.maturity import RULE_VERSION, EvidenceIn, compute_level  # noqa: E402
from services.registry import store  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "ui" / "public" / "data"

#: The permanent address of the portal. It enters the machine-readable
#: description and the sitemap, so it is written here once rather than repeated
#: across files.
SITE = "https://ragworld.org"

#: The store of the source data. Cloning remains the first way in: the artefacts
#: are derived, and the history of changes lives only here.
REPOSITORY = "https://github.com/laputski/rag-world"

#: The licence of the data and the artefacts; the same as in data/LICENSE.md.
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_NAME = "CC BY 4.0"

#: The pages of the portal that always exist. Technology cards are added to them
#: from the registry, so the sitemap never falls a record behind it.
STATIC_ROUTES = ("/", "/registry", "/changes", "/digest", "/residuals",
                 "/article", "/about")

#: The dimension schema for the interface is generated from the same declaration
#: the rest of the code uses. Writing it out by hand would mean a second
#: description of the same thing, which is exactly what this project has already
#: lived through once.
SCHEMA_MODULE = (
    Path(__file__).resolve().parent.parent / "ui" / "src" / "schema.generated.ts"
)

LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

#: The feed labels per language. A feed declares its language for the whole
#: channel, so a translation here is not a pair of fields but a second channel
#: with labels of its own.
FEED_WORDS = {
    "en": {
        "title": "RAG World: chronicle of changes",
        "description": "Maturity level changes for RAG technologies",
        "digest": "Digest for",
        "none": "none",
        "noBasis": "no basis recorded",
    },
    "ru": {
        "title": "RAG World: хроника изменений",
        "description": "Изменения уровней зрелости технологий RAG",
        "digest": "Дайджест за",
        "none": "нет",
        "noBasis": "основание не указано",
    },
}

#: The data counts as stale when the freshest evidence is older than this. The
#: mark is always shown in the interface.
STALE_AFTER = timedelta(days=45)

#: The measurement attention is derived from.
#:
#: There is no spread on the map, and that is a decision rather than an omission.
#: A point used to carry a `prevalence` field that set its size, and there was
#: nothing to fill it with: nobody wrote a series of such measurements, so all
#: sixty-two points came out the same size while the field stayed quietly empty.
#:
#: Filling it honestly does not work. Package downloads exist for seven records
#: out of sixty-two and differ by a factor of thirty thousand, from fifteen
#: hundred a month to fifty-two million. Under the old formula all seven hit the
#: largest size while the other fifty-five got the size for "no data",
#: indistinguishable from the size for "rarely downloaded": the quantity turned
#: into a mark meaning "has a Python package". On top of that the largest
#: download counts belong to OpenSearch and Qdrant, that is, to general tools
#: rather than to RAG techniques, and the map would have asserted their primacy
#: in the subject.
#:
#: Nobody collects repository stars, so the second half of the rule described a
#: source that does not exist. Adding downloads to stars is inadmissible in
#: substance too: they are different quantities in different units.
ATTENTION_METRIC = "citation_velocity"


def _built_at() -> str:
    """The moment the data is current as of, not the moment the script ran.

    The difference matters for a weekly pass. Taken from the clock, the artefacts
    differ on every run even when nothing changed, and the bot commits noise in
    which the real chronicle drowns. The date is derived from the data itself:
    the freshest piece of evidence, level change or measurement.

    The question of when anything was last checked is answered by the run log,
    which exists for that purpose.
    """
    stamps: list[str] = []
    stamps += [e.fetched_at.isoformat() for e in store.load_evidence()]
    stamps += [e.computed_at.isoformat() for e in store.load_levels()]
    stamps += [m.measured_at.isoformat() for m in store.load_metrics()]
    if not stamps:
        # No data at all: the date comes from the clock, there being nowhere
        # else to take it from.
        return datetime.now(timezone.utc).date().isoformat()
    return max(stamps)


def _latest_metric(points: list[store.MetricPoint], metric: str) -> float | None:
    """The freshest measurement of a quantity for one record.

    A record may have several works, and each is measured separately. Freshness
    is therefore computed **per source**, and only then are the sources brought
    together. The order matters, and the reverse order spoils the data.

    It used to take the freshest date across the whole record and the largest
    value within it. One source failing to answer on a given pass was enough to
    drop it from the calculation entirely, the freshest date by then belonging to
    another source. That is how the attention of Dense X fell from 1.089 to 0.101
    — not because the work stopped being cited, but because its second work could
    not be polled that day. For an unattended pass this is the worst kind of
    breakage: the number changes tenfold and looks like an observation.

    The sources are combined by taking the largest value, and that choice is not
    arbitrary either:

    * taking the first one will not do, because the quantity would depend on the
      order of lines in a file, that is, on which link entered the record first;
    * adding them will not do, because a preprint and its conference version
      exist in the index as two works, and a sum would count one work twice.

    The largest is the attention paid to the most visible work of a record. It is
    not inflated: a measurement of that size genuinely exists.
    """
    relevant = [p for p in points if p.metric == metric]
    if not relevant:
        return None
    by_source: dict[str, store.MetricPoint] = {}
    for point in relevant:
        known = by_source.get(point.source)
        if known is None or (point.measured_at, point.value) > (
            known.measured_at, known.value
        ):
            by_source[point.source] = point
    return max(p.value for p in by_source.values())


#: The prose of the records: a short summary and a full description of each.
#:
#: The texts live in the interface localisation resources, because they are
#: written together with the interface and edited more often than the data. They
#: are copied into the artefact: the registry, once published, consisted of
#: codes, levels and links without a single sentence saying what a technology
#: was, and reading it without the portal was impossible. Both languages are
#: copied at once, or the published data comes out half in a language the
#: consumer does not read.
PROSE_DIR = Path(__file__).resolve().parent.parent / "ui" / "src" / "i18n"

#: A prose field and the name it goes out under in the artefact. The short
#: summary is called `summary` rather than `short`: outside the interface
#: "short" does not say short what.
PROSE_FIELDS = (
    ("short", "summary"),
    ("full", "description"),
    ("problem", "problem"),
    ("barriers", "barriers"),
    ("solutions", "solutions"),
    ("maturityNote", "maturity_note"),
)


def _prose() -> dict[str, dict[str, str]]:
    """The prose per record in both languages, ready for the artefact."""
    tables = {
        language: json.loads(
            (PROSE_DIR / language / "tech.json").read_text(encoding="utf-8")
        )
        for language in ("ru", "en")
    }
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for prose_id in tables["ru"]:
        for source_field, published in PROSE_FIELDS:
            russian = tables["ru"].get(prose_id, {}).get(source_field)
            english = tables["en"].get(prose_id, {}).get(source_field)
            if russian:
                out[prose_id][published] = russian
            if english:
                out[prose_id][f"{published}_en"] = english
    return dict(out)


def _strata_rows() -> list[dict]:
    """The strata with their names in both languages.

    The names come from the interface resources rather than from the schema: in
    the schema they exist in one language only, and the artefact would carry half
    a label. The letter prefix of the form "A. " is stripped, because the stratum
    code stands beside it as a field of its own.
    """
    names = {
        language: json.loads(
            (PROSE_DIR / f"{language}.json").read_text(encoding="utf-8")
        )["stratum"]
        for language in ("ru", "en")
    }
    strip = lambda label: label.split(". ", 1)[-1]  # noqa: E731
    return [
        {
            "code": code,
            "name": strip(names["ru"].get(code, russian)),
            "name_en": strip(names["en"].get(code, code)),
        }
        for code, russian in STRATA.items()
    ]


def _parse_notes() -> dict[str, list[dict]]:
    """The justifications of the reading, per record.

    The configuration is the one part of the portal where a person made the
    decision rather than a rule. A level shows the output of the rule and a piece
    of evidence shows its source; without a justification a dimension value stays
    a claim the reader has no means to check, and it is also the most subjective
    thing on the card.
    """
    path = store.DATA_DIR / "parse_notes.jsonl"
    if not path.exists():
        return {}
    notes: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            note = json.loads(line)
            notes[note["technology_id"]].append(note)
    return notes


def _candidate_queue() -> list[dict]:
    """The candidates awaiting a verdict, the newest first.

    Those already decided do not enter the queue: an accepted candidate has
    become a registry record, and a refused one is written into the file of
    refusals with its reason. Showing them would mean passing work already done
    off as work still to do.
    """
    path = store.DATA_DIR / "candidates.jsonl"
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pending = []
    for row in rows:
        if row.get("verdict"):
            continue
        # The abstract is cut for display: a reader needs it to decide whether
        # to open the work, and it stays whole in the data. The cut goes on a
        # sentence boundary, or the phrase breaks mid-word.
        abstract = (row.get("abstract") or "").strip()
        if len(abstract) > CANDIDATE_ABSTRACT_LIMIT:
            cut = abstract[:CANDIDATE_ABSTRACT_LIMIT]
            stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            abstract = (cut[: stop + 1] if stop > 200 else cut.rstrip() + "…")
        pending.append({**row, "abstract": abstract})
    # Ordered by fitness: the queue exists to be reviewed, and what is likelier
    # to fit should be looked at first. On equal fitness the newer comes first.
    return sorted(
        pending,
        key=lambda r: ((r.get("fit") or {}).get("score", 0),
                       r.get("published") or "", r["arxiv_id"]),
        reverse=True,
    )


#: How many characters of an abstract to show. Two or three sentences are enough
#: to tell what a work is about; the whole abstract opens through the link to the
#: source.
CANDIDATE_ABSTRACT_LIMIT = 480


def _residual_vocabulary() -> dict[str, dict]:
    path = store.DATA_DIR / "residual_vocabulary.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in payload.get("mechanisms", [])}


def _residual_term(code: str, lang: str = "ru") -> str:
    """The wording of a residual mechanism, by its code.

    An unknown code is returned as it is: data validation will not let such a
    record through, and the build must not silently turn an error into a blank.
    """
    entry = _residual_vocabulary().get(code)
    return entry.get(lang, code) if entry else code


#: How many mentions make a residual mechanism a candidate dimension. Three is
#: not magic but a reasonable minimum: one case happens to any work, two may be
#: a coincidence, and three times running the schema is no longer missing by
#: chance.
RESIDUAL_CANDIDATE_THRESHOLD = 3


def _residual_queue(technologies: list[store.Technology]) -> list[dict]:
    """The residual mechanisms with their counts and the records they appear in.

    The point of the queue is that the schema should grow from observation rather
    than from imagination. A mechanism that has to be written into a residual
    again and again marks a place where the schema is too small; a mechanism met
    once is a particularity of one work.
    """
    vocabulary = _residual_vocabulary()
    seen: dict[str, list[dict]] = defaultdict(list)
    for tech in technologies:
        for code in tech.residual:
            seen[code].append({"id": tech.id, "name": tech.name})

    rows = []
    for code, users in seen.items():
        entry = vocabulary.get(code, {})
        rows.append({
            "id": code,
            "term": entry.get("ru", code),
            "term_en": entry.get("en", code),
            "note": entry.get("note", ""),
            "note_en": entry.get("note_en", entry.get("note", "")),
            "count": len(users),
            "technologies": sorted(users, key=lambda u: u["name"]),
            "candidate": len(users) >= RESIDUAL_CANDIDATE_THRESHOLD,
        })
    return sorted(rows, key=lambda r: (-r["count"], r["term"]))


#: Below this size an age subgroup is not normalised: a median over three values
#: is unstable and shifts more from one new work appearing than from anything
#: happening in the field.
MIN_COHORT = 5


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def attention_cohorts(
    technologies: list[store.Technology],
    metrics_by_tech: dict[str, list[store.MetricPoint]],
) -> dict[str, float]:
    """The median citation velocity by year of first publication.

    Velocities cannot be compared directly: a work two years old has had longer
    to gather citations than one published the day before yesterday, and without
    normalisation the old always looks more popular than the new. Normalising
    inside an age subgroup removes that bias.
    """
    by_year: dict[str, list[float]] = defaultdict(list)
    for tech in technologies:
        if not tech.first_published:
            continue
        value = _latest_metric(
            metrics_by_tech.get(tech.id, []), ATTENTION_METRIC
        )
        if value is not None:
            by_year[tech.first_published[:4]].append(value)
    return {
        year: _median(values)
        for year, values in by_year.items()
        if len(values) >= MIN_COHORT and _median(values) > 0
    }


def normalized_attention(
    tech: store.Technology,
    metrics_by_tech: dict[str, list[store.MetricPoint]],
    cohorts: dict[str, float],
) -> dict[str, object]:
    """Attention in three forms: measured, normalised, and its provenance.

    All three are returned because each answers a different question. What the
    reader is shown is the normalised value, but the provenance has to be
    available, and without the raw value there is no checking it.
    """
    raw = _latest_metric(metrics_by_tech.get(tech.id, []), ATTENTION_METRIC)
    if raw is None:
        return {"attention": None, "attention_raw": None, "attention_cohort": None}

    year = (tech.first_published or "")[:4]
    median = cohorts.get(year)
    if median is None:
        # The subgroup is too small or the year is unknown: there is nothing to
        # normalise by. What is shown is the measured value with a mark, not an
        # invented normalised one.
        return {
            "attention": raw,
            "attention_raw": raw,
            "attention_cohort": None,
        }
    return {
        "attention": round(raw / median, 3),
        "attention_raw": raw,
        "attention_cohort": year,
    }


def build(out_dir: Path | None = None) -> dict[str, int]:
    """Build the artefacts. `out_dir` is substituted by the drift check."""
    technologies = store.load_technologies()
    evidence = store.load_evidence()
    levels = store.load_levels()
    metrics = store.load_metrics()

    evidence_by_tech: dict[str, list[store.Evidence]] = defaultdict(list)
    for item in evidence:
        evidence_by_tech[item.technology_id].append(item)

    metrics_by_tech: dict[str, list[store.MetricPoint]] = defaultdict(list)
    for point in metrics:
        metrics_by_tech[point.technology_id].append(point)

    level_by_tech: dict[str, store.LevelEntry] = {}
    history_by_tech: dict[str, list[store.LevelEntry]] = defaultdict(list)
    for entry in levels:
        level_by_tech[entry.technology_id] = entry  # the journal is ordered in time
        history_by_tech[entry.technology_id].append(entry)

    cohorts = attention_cohorts(technologies, metrics_by_tech)
    parse_notes = _parse_notes()
    prose = _prose()

    built_at = _built_at()
    freshest = max((e.fetched_at for e in evidence), default=None)
    stale = freshest is None or (date.today() - freshest) > STALE_AFTER

    # ─── The registry ────────────────────────────────────────────────────────
    registry_rows = []
    for tech in technologies:
        entry = level_by_tech.get(tech.id)
        tech_evidence = evidence_by_tech.get(tech.id, [])

        # The output of the rule travels with the record so that a card can show
        # why the level is what it is and what is missing for the next one.
        # Without that a level stays a claim the reader has no means to check.
        reasoning = None
        if tech_evidence:
            result = compute_level([
                EvidenceIn(
                    type=e.type, source=e.source, value=e.value,
                    fetched_at=e.fetched_at, verified=e.verified,
                )
                for e in tech_evidence
            ])
            reasoning = {
                "satisfied": result.satisfied,
                "missing": result.missing,
                "confidence": round(result.confidence, 3),
                "evidence_basis": result.evidence_basis,
            }

        registry_rows.append({
            **tech.model_dump(mode="json"),
            **prose.get(tech.prose_id or "", {}),
            # The data stores the code of a mechanism, and the reader needs the
            # wording. The substitution happens at build time rather than in the
            # registry: translating the vocabulary then requires no rewriting of
            # the technology records.
            "residual": [_residual_term(code) for code in tech.residual],
            "residual_en": [_residual_term(code, "en") for code in tech.residual],
            # The justification of the reading: why a dimension holds the value
            # it does. A residual gets its wording from the vocabulary so that a
            # card never shows a bare code.
            "parse_notes": [
                {
                    **note,
                    "residual_term": (
                        _residual_term(note["residual"]) if note.get("residual") else None
                    ),
                    "residual_term_en": (
                        _residual_term(note["residual"], "en")
                        if note.get("residual") else None
                    ),
                }
                for note in parse_notes.get(tech.id, [])
            ],
            "level": entry.level if entry else None,
            "confidence": entry.confidence if entry else None,
            "evidence_basis": entry.evidence_basis if entry else None,
            # The registry table needs attention too: one of its orderings uses it.
            **normalized_attention(tech, metrics_by_tech, cohorts),
            "evidence_count": len(tech_evidence),
            "evidence": [
                {
                    "type": e.type,
                    "value": e.value,
                    "value_en": e.value_en,
                    "source": e.source,
                    "fetched_at": e.fetched_at.isoformat(),
                    "obtained_by": e.obtained_by,
                }
                for e in tech_evidence
            ],
            "level_reason": reasoning,
        })

    # ─── The map ─────────────────────────────────────────────────────────────
    points = []
    for tech in technologies:
        entry = level_by_tech.get(tech.id)
        points.append({
            "id": tech.id,
            "name": tech.name,
            "kind": tech.kind,
            # The first stratum sets the colour; the whole set is for filtering.
            "group": tech.groups[0] if tech.groups else None,
            "groups": tech.groups,
            # An absent level stays absent: substituting L0 is inadmissible, or
            # "not studied" becomes indistinguishable from "a hypothesis".
            "level": entry.level if entry else None,
            "confidence": entry.confidence if entry else None,
            "evidence_basis": entry.evidence_basis if entry else None,
            **normalized_attention(tech, metrics_by_tech, cohorts),
            "first_published": tech.first_published,
            "prose_id": tech.prose_id,
            # The map needs the history to show movement over a period: without
            # it the freshness of the data stays a claim rather than something
            # observed.
            "history": [
                {"level": h.level, "at": h.computed_at.isoformat()}
                for h in history_by_tech.get(tech.id, [])
            ],
        })

    map_artifact = {
        "built_at": built_at,
        "rule_version": RULE_VERSION,
        "levels": LEVELS,
        "strata": _strata_rows(),
        "points": points,
        "count": len(points),
        "stale": stale,
    }

    # ─── The chronicle ───────────────────────────────────────────────────────
    order = {level: i for i, level in enumerate(LEVELS)}
    previous: dict[str, str] = {}
    changes = []
    names = {t.id: t.name for t in technologies}
    for entry in levels:
        before = previous.get(entry.technology_id)
        if before is None:
            kind = "added"
        elif order.get(entry.level, 0) > order.get(before, 0):
            kind = "level_up"
        else:
            kind = "level_down"
        previous[entry.technology_id] = entry.level
        changes.append({
            "technology_id": entry.technology_id,
            "name": names.get(entry.technology_id, entry.technology_id),
            "kind": kind,
            "level_before": before,
            "level_after": entry.level,
            "evidence": entry.evidence_snapshot,
            "changed_at": entry.computed_at.isoformat(),
        })
    changes.sort(key=lambda c: c["changed_at"], reverse=True)

    # ─── The summary ─────────────────────────────────────────────────────────
    # Every level is listed, the empty ones included.
    #
    # The counter used to create a key only where a record was found, so L6 fell
    # out of the summary entirely: the scale looked as though it ended at L5,
    # whereas "no technology has reached an industry standard" is arguably the
    # most substantial thing the scale says.
    #
    # This does not contradict the rule that a zero must never stand in for an
    # absence: here the zero is the observation, and "we do not know" lives under
    # a key of its own, `unknown`.
    counted = Counter(
        (level_by_tech[t.id].level if t.id in level_by_tech else "unknown")
        for t in technologies
    )
    by_level = {level: counted.get(level, 0) for level in LEVELS}
    by_level["unknown"] = counted.get("unknown", 0)
    by_stratum: Counter[str] = Counter()
    for tech in technologies:
        for group in tech.groups:
            by_stratum[group] += 1

    stats = {
        "built_at": built_at,
        "total": len(technologies),
        "by_level": by_level,
        "by_kind": dict(sorted(Counter(t.kind for t in technologies).items())),
        "by_stratum": dict(sorted(by_stratum.items())),
        "with_evidence": sum(1 for t in technologies if evidence_by_tech.get(t.id)),
        "with_level": len(level_by_tech),
        "with_attention": sum(1 for p in points if p["attention"] is not None),
        "evidence_total": len(evidence),
        "freshest_evidence": freshest.isoformat() if freshest else None,
        "stale": stale,
    }

    # ─── Writing ─────────────────────────────────────────────────────────────
    target = out_dir or OUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    _write(target / "registry.json", {
        "built_at": built_at,
        "count": len(registry_rows),
        "technologies": registry_rows,
    })
    _write(target / "map.json", map_artifact)
    _write(target / "changes.json", {"built_at": built_at, "changes": changes})
    _write(target / "stats.json", stats)
    # Digest issues are data rather than something derived: they are appended by
    # a separate step and only laid out here for the portal to read, newest
    # first.
    _write(target / "digest.json", {"built_at": built_at, "issues": _issues()})
    # The candidate queue: work found by the catalogue and awaiting a person's
    # verdict. Discovery creates no records, so a candidate stays a supposition
    # until the owner accepts or refuses it.
    _write(target / "candidates.json", {
        "built_at": built_at,
        "candidates": _candidate_queue(),
    })
    _write(target / "residuals.json", {
        "built_at": built_at,
        "candidate_threshold": RESIDUAL_CANDIDATE_THRESHOLD,
        "mechanisms": _residual_queue(technologies),
    })
    # A feed declares its language for the whole channel, so there are two feeds
    # rather than one with fields in two languages.
    #
    # Each record is also published as a file of its own. A technology card used
    # to read the whole registry for a single record: eight hundred kilobytes for
    # the page people most often arrive at from an outside link. A file per
    # record costs about ten kilobytes and holds the same thing, so a consumer
    # who wants one technology does not pay for the rest.
    per_record = target / "tech"
    per_record.mkdir(parents=True, exist_ok=True)
    stale = {path.name for path in per_record.glob("*.json")}
    for row in registry_rows:
        _write(per_record / f"{row['id']}.json", {"built_at": built_at, "technology": row})
        stale.discard(f"{row['id']}.json")
    # A record removed from the registry must not stay reachable by a link.
    for name in stale:
        (per_record / name).unlink()

    _write_feed(target / "feed.xml", changes, built_at, _issues(), "en")
    _write_feed(target / "feed.ru.xml", changes, built_at, _issues(), "ru")
    # The machine-readable entrance: the dataset description, the sitemap and the
    # pointer for language models. They are built here because they depend on the
    # same numbers as the artefacts, and built apart they would diverge from them
    # at the first new record.
    _write(target / "index.json", _access_manifest(target, built_at, registry_rows, stats))
    _write_sitemap(target.parent / "sitemap.xml", registry_rows, built_at)
    (target.parent / "llms.txt").write_text(
        render_llms_txt(built_at, registry_rows, stats), encoding="utf-8"
    )
    if out_dir is None:
        SCHEMA_MODULE.write_text(render_schema_module(), encoding="utf-8")

    return {
        "technologies": len(registry_rows),
        "points": len(points),
        "changes": len(changes),
        "with_level": len(level_by_tech),
    }


def render_schema_module() -> str:
    """The TypeScript module of the schema, generated from the declaration."""
    strata = ",\n".join(
        f'  {{ code: "{code}", name: {json.dumps(name, ensure_ascii=False)} }}'
        for code, name in STRATA.items()
    )
    dimensions = ",\n".join(
        "  {{ code: \"{code}\", name: {name}, stratum: \"{stratum}\", "
        "core: {core}, default: \"{default}\", values: {values} }}".format(
            code=d.code,
            name=json.dumps(d.name, ensure_ascii=False),
            stratum=d.group,
            core="true" if d.core else "false",
            default=d.default,
            values=json.dumps(list(d.values), ensure_ascii=False),
        )
        for d in DIMENSIONS
    )
    return (
        "// GENERATED from core/dimensions_schema.py by `make artifacts`.\n"
        "// Do not edit by hand: the edit would be lost and the schema would end\n"
        "// up described twice.\n"
        "\n"
        "export interface DimensionSpec {\n"
        "  code: string;\n"
        "  name: string;\n"
        "  stratum: string;\n"
        "  core: boolean;\n"
        "  default: string;\n"
        "  values: string[];\n"
        "}\n"
        "\n"
        f"export const SCHEMA_SIZE = {SCHEMA_SIZE};\n"
        "\n"
        "export const STRATA: { code: string; name: string }[] = [\n"
        f"{strata},\n"
        "];\n"
        "\n"
        "export const DIMENSIONS: DimensionSpec[] = [\n"
        f"{dimensions},\n"
        "];\n"
        "\n"
        "/** The dimensions of a stratum, in the order they are declared. */\n"
        "export function dimensionsOf(stratum: string): DimensionSpec[] {\n"
        "  return DIMENSIONS.filter((d) => d.stratum === stratum);\n"
        "}\n"
    )


#: The datasets the portal publishes: the file, the key holding the records, and
#: what each is for.
#:
#: The descriptions are in English deliberately. They are read not by a visitor
#: but by whoever connects the dataset to their own system, and in that role
#: English is the common language.
DATASETS: tuple[tuple[str, str, str], ...] = (
    ("registry.json", "technologies",
     "Every technology in the registry with its configuration over the 28 "
     "dimensions, maturity level, the rule output behind that level, and the "
     "evidence records the level stands on."),
    ("map.json", "points",
     "Maturity level against attention for every record, as plotted on the "
     "maturity map."),
    ("changes.json", "changes",
     "Append-only chronicle: every level change with its date and the "
     "evidence that caused it."),
    ("stats.json", "",
     "Counts by kind, level, and stratum, plus the date of the freshest "
     "evidence."),
    ("residuals.json", "mechanisms",
     "Mechanisms recorded as not expressible in the current schema, with the "
     "records that raised each one. Three mentions make a mechanism a "
     "candidate for a new dimension."),
    ("candidates.json", "candidates",
     "Works found by weekly discovery and awaiting a human verdict, each with "
     "a deterministic fit score from 0 to 10."),
    ("digest.json", "issues",
     "Digest issues, generated from the chronicle without a language model."),
)


def _access_manifest(target: Path, built_at: str, rows: list[dict], stats: dict) -> dict:
    """The dataset description for a machine consumer.

    The artefacts sat in an open directory before this too, but the only way to
    learn they existed was to read the portal's source. The index names every
    dataset, what it is for and how many records it holds, so connecting to it
    requires neither parsing pages nor reading code.

    The record counts are taken from the files just written rather than from the
    build state. The index therefore describes what was published rather than
    what was intended, and cannot diverge from it.
    """
    datasets = []
    for name, key, description in DATASETS:
        entry: dict = {
            "url": f"{SITE}/data/{name}",
            "description": description,
        }
        if key:
            payload = json.loads((target / name).read_text(encoding="utf-8"))
            entry["records_at"] = key
            entry["records"] = len(payload.get(key, []))
        datasets.append(entry)

    return {
        "name": "RAG World",
        "site": SITE,
        "built_at": built_at,
        "license": {"name": LICENSE_NAME, "url": LICENSE_URL},
        "attribution": f"RAG World, {SITE}",
        "repository": REPOSITORY,
        "documentation": f"{SITE}/about",
        "schema": {
            "dimensions": SCHEMA_SIZE,
            "strata": _strata_rows(),
            "levels": LEVELS,
            "rule_version": RULE_VERSION,
        },
        "technologies": len(rows),
        "technology_ids": sorted(row["id"] for row in rows),
        "datasets": datasets,
        # One record at a time: the address is built by substitution, which is
        # more use to a consumer of the dataset than a full list of sixty-nine
        # addresses.
        "technology": {
            "url_template": f"{SITE}/data/tech/{{id}}.json",
            "description": "One registry record on its own, in the same shape as "
                           "a row of registry.json. Use it when a single "
                           "technology is wanted: the full registry costs "
                           "eighty times more.",
        },
        # Releases are immutable: a link to a record inside a release points at
        # something that will not change, whereas a link to the current artefact
        # points at a moving object. Only the first is fit for a citation.
        "releases": f"{SITE}/data/releases/index.json",
        # The feeds are named by language: a channel declares its language for
        # all of itself, so there are two, and a consumer needs to know which is
        # which.
        "feeds": {
            "en": f"{SITE}/data/feed.xml",
            "ru": f"{SITE}/data/feed.ru.xml",
        },
        "sitemap": f"{SITE}/sitemap.xml",
    }


def _write_sitemap(path: Path, rows: list[dict], built_at: str) -> None:
    """The sitemap over the permanent pages and the registry cards."""
    day = built_at[:10]
    urls = [f"{SITE}{route}" for route in STATIC_ROUTES]
    urls += [f"{SITE}/tech/{row['id']}" for row in sorted(
        rows, key=lambda r: r["id"]
    )]
    body = "\n".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{day}</lastmod></url>"
        for url in urls
    )
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n",
        encoding="utf-8",
    )


def render_llms_txt(built_at: str, rows: list[dict], stats: dict) -> str:
    """The portal's pointer for language models.

    The llmstxt.org convention: a short file at the root from which it is clear
    what the site holds and where that sits in machine-readable form. Its point
    is that a model needing information about RAG technologies should take it
    from the data rather than parse the pages: parsing pages gives a worse result
    and breaks at the first edit to the layout.
    """
    lines = [
        "# RAG World",
        "",
        "> A self-updating registry of retrieval-augmented generation "
        "technologies. Every record carries a configuration over a 28-dimension "
        "schema, a maturity level from L0 to L6 derived by a deterministic rule "
        "with no language model involved, and the evidence that level stands on. "
        "Data is collected weekly from arXiv, OpenAlex, GitHub, PyPI and Papers "
        "with Code.",
        "",
        "Do not scrape the pages. Every page on this site is rendered from the "
        "JSON files below, and those files are the same data without the markup. "
        f"Start from {SITE}/data/index.json, which lists them all.",
        "",
        f"- Records: {len(rows)}",
        f"- Evidence records: {stats.get('evidence_total')}",
        f"- Freshest evidence: {stats.get('freshest_evidence')}",
        f"- Built: {built_at}",
        f"- Licence: {LICENSE_NAME}, {LICENSE_URL}",
        f"- Attribution: RAG World, {SITE}",
        "",
        "## Data",
        "",
        f"- [Index of all datasets]({SITE}/data/index.json): what each file "
        "holds, how many records, where the schema is described.",
    ]
    for name, _key, description in DATASETS:
        title = name.removesuffix(".json").replace("_", " ").capitalize()
        lines.append(f"- [{title}]({SITE}/data/{name}): {description}")
    lines += [
        "",
        "## Citing",
        "",
        f"- [Releases]({SITE}/data/releases/index.json): dated, immutable "
        "snapshots. Cite a release, not the live file: the live file changes "
        "every week.",
        f"- [How to cite]({SITE}/about): citation formats and the licence.",
        "",
        "## Source",
        "",
        f"- [Repository]({REPOSITORY}): the data lives in git as one JSON file "
        "per technology, plus append-only evidence and level journals. Cloning "
        "gives the full history; the artefacts above are derived from it.",
        "",
    ]
    return "\n".join(lines)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _issues() -> list[dict]:
    """The digest issues, newest first."""
    directory = store.DATA_DIR / "digest"
    if not directory.exists():
        return []
    issues = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
    return sorted(issues, key=lambda i: i["issued_at"], reverse=True)


def _write_feed(
    path: Path, changes: list[dict], built_at: str,
    issues: list[dict] | None = None, language: str = "en",
) -> None:
    """The feed: digest issues and level changes.

    The issues come first: a reader of the feed wants the message about the pass,
    and the individual level changes serve as its detail.

    A feed carries one language by construction, declared for the whole channel,
    so fields in two languages cannot go into one channel. Hence two feeds,
    `feed.xml` in English and `feed.ru.xml` in Russian, each declaring its
    language in the markup so that a reader need not guess.
    """
    words = FEED_WORDS[language]
    items = []
    for issue in (issues or [])[:20]:
        text = issue.get("text_en" if language == "en" else "text") or issue.get("text", "")
        items.append(
            "    <item>\n"
            f"      <title>{escape(words['digest'] + ' ' + issue['issued_at'])}</title>\n"
            f"      <description>{escape(text)}</description>\n"
            f"      <guid isPermaLink=\"false\">digest-{escape(issue['issued_at'])}</guid>\n"
            "    </item>"
        )
    for change in changes[:50]:
        before = change["level_before"] or words["none"]
        title = f"{change['name']}: {before} > {change['level_after']}"
        body = ", ".join(
            f"{e.get('type', '')} {e.get('source', '')}".strip()
            for e in change["evidence"][:5]
        ) or words["noBasis"]
        items.append(
            "    <item>\n"
            f"      <title>{escape(title)}</title>\n"
            f"      <description>{escape(body)}</description>\n"
            f"      <guid isPermaLink=\"false\">{escape(change['technology_id'])}"
            f"-{escape(change['changed_at'])}-{escape(change['level_after'])}</guid>\n"
            "    </item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{escape(words['title'])}</title>\n"
        f"    <description>{escape(words['description'])}</description>\n"
        f"    <language>{language}</language>\n"
        f"    <link>{SITE}/changes</link>\n"
        f"    <lastBuildDate>{escape(built_at)}</lastBuildDate>\n"
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )
    path.write_text(feed, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    counts = build()
    print(
        f"Artefacts built: technologies {counts['technologies']}, "
        f"map points {counts['points']}, chronicle entries {counts['changes']}, "
        f"with a computed level {counts['with_level']}"
    )
    print(f"Directory: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
