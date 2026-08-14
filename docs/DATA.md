# The registry of RAG technologies

The single source of facts about RAG technologies. Every view of the portal
reads from here and from nowhere else. The registry lives in `data/` as
versioned files: those files are the project's database.

The registry carries no version number of its own: what a consumer needs to
pin is a release, and every release is a dated, immutable snapshot. What the
published `index.json` does carry is the version of the rule that derives a
level, because two levels are comparable only under the same rule.

The grounds for this arrangement are recorded in
[`governance/DECISIONS.md`](../governance/DECISIONS.md), ADR-003 and ADR-004.

## Why files and not a database

The portal is hosted as static files and updates itself without a person. The
free managed database on the hosting platform expires thirty days after it is
created, which means a person has to intervene every month — exactly what the
project is built to avoid.

Files under version control give for nothing what a database would have to be
made to do:

| What is required | How a file gets it |
|---|---|
| evidence is only ever appended | a commit is immutable by definition |
| every change has a provenance | the history of edits to the file |
| the state on any past date | any revision of the tree |
| changes approved by a person | a pull request |
| open data for a reader | the file is already machine-readable and downloads from a link |

The fields below match the schema of the earlier relational tables, so importing
the registry into a database or an analytical engine stays available should it
ever be wanted.

## Layout

```
data/
  technologies/<id>.json     the facts about one technology, one file per record
  evidence/YYYY-MM.jsonl     evidence, append-only, partitioned by month
  metrics/YYYY.jsonl         the series of attention and spread
  levels/history.jsonl       the journal of maturity-level changes
  manual_evidence.jsonl      evidence entered by a person
  parse_notes.jsonl          why each configuration value was read that way
  candidates.jsonl           work found by discovery, awaiting a verdict
  rejected.jsonl             candidates refused, with the reason
  collection_log.jsonl       one line per collection pass
  residual_vocabulary.json   the coded mechanisms a residual may name
  digest/YYYY-MM-DD.json     digest issues, one per file
```

The layout is chosen so that an update touches as few files as possible. A
change to one technology changes one file, so the difference reads by eye and
the history of a single record stays surveyable. A month of evidence, once
closed, is never rewritten again.

### `technologies/<id>.json` — the facts

| Field | Type | What it holds |
|---|---|---|
| `id` | string | a stable lower-case identifier, never changed after creation |
| `name` | string | the canonical name |
| `aliases` | list of strings | spellings used for deduplication |
| `kind` | string | `paradigm`, `architecture`, `technique`, `tool`, `artifact`, `attack` |
| `family` | string | the family in the classification of the field |
| `groups` | list of strings | the strata A–G the contribution belongs to |
| `configuration` | object | the dimension values; the field two records are compared by |
| `configuration_variable` | list of strings | dimensions the system chooses at run time |
| `configuration_inapplicable` | list of strings | dimensions that assert nothing about this object |
| `configuration_reviewed` | date | when the configuration was read out of the sources |
| `residual` | list of strings | mechanisms the schema does not express, as codes |
| `prose_id` | string | the link to the localised prose of the record |
| `first_published` | string | the year and month of first publication |
| `package` | string | the name in the Python package index, when one exists |
| `links` | list of objects | the sources: address, kind, label, check status, check date |

Long texts do not go into this file: the prose lives in the localisation
resources and is joined through `prose_id`.

Three states of a dimension are distinguished, and the distinction carries
meaning. A value present in `configuration` is an assertion about the system. A
dimension listed in `configuration_inapplicable` has no value at all, because a
retriever has no synthesis stage and "generation is single-pass" would assert
something about what does not exist. A dimension absent from both, in a record
whose `configuration_reviewed` is empty, means nobody has read it yet — which is
not the same as agreeing with the base configuration.

### `evidence/YYYY-MM.jsonl` — the evidence

One record per line: `technology_id`, `type`, `value`, `value_en`, `source`,
`fetched_at`, `obtained_by`, `verified`. The admissible types are a publication,
an independent reproduction, the state of a repository, a successful build and
run, presence in a framework, package downloads, industrial use, and the number
of independent providers.

Evidence is never rewritten. A change of level is always explicable by the
evidence available when it was computed.

### `manual_evidence.jsonl` — what exists in no machine-readable form

The open indexes do not cover everything. Publications at venues that issue no
digital identifiers, industrial use, and independent reproductions enter the
registry only through this file. The format matches that of the evidence, the
means of obtaining always names a person, and a link to the confirmation is
mandatory.

This is not a loophole but an admission of a boundary. Without such a route, an
industrial technique described in a provider's note and applied everywhere would
rank below a preprint nobody has reproduced. The provenance stays visible: the
interface tells such evidence from what was collected automatically.

### `metrics/YYYY.jsonl` — the series

One record per line: `technology_id`, `metric`, `value`, `measured_at`,
`source`. This is the one part of the registry that grows linearly with time.
Nothing thins it yet; when the growth begins to matter, the intended policy is
to reduce series older than twenty-four months to one point a month.

### `levels/history.jsonl` — the level journal

One record per line: `technology_id`, `level`, `confidence`, `evidence_basis`,
`rule_version`, `computed_at`, `evidence_snapshot`. A record is added **only
when the level changes**, not on every recomputation, so the journal stays short
and reads as a chronicle.

`evidence_basis` distinguishes a computed level from one entered by a person:
for industrial operation and for an industry standard no machine-readable source
exists, and that is not disguised as a computation.

### `parse_notes.jsonl` — why a value was read that way

One record per line: the technology, the dimension `code`, the value `to`, and
four fields of justification — what the system `did`, what it does `instead` of
the base behaviour, `why` that reading follows, and the `source` it follows
from. Each has an `_en` twin.

A level is computed from evidence and reproduces. A dimension value is a
conclusion drawn from the text of a paper, and the only way to check it is the
reasoning that led to it. This file holds that reasoning, and
`scripts/build_review.py` renders it as a page.

### `candidates.jsonl` and `rejected.jsonl` — the discovery queue

A work that has been found is not a technology but a supposition about one.
Discovery appends candidates with their fitness score and leaves the verdict to
a person. A refused candidate moves to `rejected.jsonl` together with the reason
and the date, so that the decision is not forgotten and the candidate does not
surface again.

### `collection_log.jsonl` — that the pass happened

One line per collection pass, written whether anything changed or not. It
separates "the data is old because nobody looked" from "the data is old because
nothing happened", and it gives the hosting platform a sign of activity: a
schedule is disabled after sixty days without commits, and a line of this
journal is a commit.

## The artefacts built from it

The files the portal reads are built from the registry deterministically:

```
ui/public/data/
  index.json       the index of datasets: what is in each file and how many records
  registry.json    the whole registry; filtering happens in the browser
  tech/<id>.json   one record on its own, for readers who do not want all of it
  map.json         the points of the maturity map, the level and stratum bands
  changes.json     the chronicle of changes, each linked to its evidence
  stats.json       the summary: distribution by level, coverage, freshness
  residuals.json   the residual queue: mechanisms the schema does not express
  candidates.json  the candidate queue: what has been found and awaits a decision
  digest.json      the digest issues
  feed.xml         the chronicle as a feed, in English
  feed.ru.xml      the same in Russian: a feed declares one language for all of it
  releases/        dated snapshots that never change, and their index
```

The artefacts are bilingual: a record's description comes out as `summary` and
`description` with `_en` twins beside them, and a Russian text without its twin
never reaches the published data.

`sitemap.xml`, `llms.txt` and the icons are built alongside from the same data,
so they do not fall a record behind the registry.

Rebuild them with `make artifacts` and check them with `make validate`: schema,
resolvable links, and no number without a provenance.

## Conventions

**Identifiers.** Lower-case Latin letters, digits and underscores only. An
identifier never changes after creation, because record pages and external
citations point at it. A product with an owner takes the owner's prefix.

**Kinds.** A paradigm constrains dimension values without fixing a full
configuration. An architecture fixes a full or nearly full configuration. A
technique fixes the value of one dimension. A tool implements part of a
constructor and is not a point of the configuration space. An evaluation
artefact serves to measure. An attack acts upon a RAG system from outside and
therefore holds no configuration at all.

Comparing levels across kinds misleads: a technique enters a framework as one
function, while a whole architecture travels the same road with markedly more
difficulty. The kind is therefore always shown and takes part in filtering.
