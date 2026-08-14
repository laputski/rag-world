# Contributing to RAG World

Thank you for considering it. This registry exists to be checked, and a
correction is as welcome as an addition.

Read this page before opening anything: the rules below are what keep the
registry worth citing, and a contribution that ignores them costs more to
review than to write.

## The one rule everything follows

**Nothing enters the registry without a resolvable source.**

A name without a link is a mention, not a technology. A level without evidence
is an opinion. A configuration value without a reason is a guess. If you cannot
point at something a reader can open, the contribution is not ready — and that
is a statement about the sources, not about you.

## What is accepted

**A new record.** A technology with a resolvable primary source: a preprint, a
peer-reviewed paper, or vendor documentation of a real deployment. Marketing
pages and blog explainers that cite nothing do not count as primary sources.

**A correction to a configuration.** If a dimension was read wrongly from the
source, say which dimension, what it should be, and which passage of the source
says so. These are the most valuable contributions: the configuration is the
only part of the registry where a human made the call.

**Evidence we missed.** A peer-reviewed venue for something we have as a
preprint, an independent reimplementation, documented production use. Include
the link.

**A residual.** A mechanism a record uses that the twenty-eight dimensions
cannot express. Residuals are how the schema grows: three records naming the
same mechanism make it a candidate dimension.

**Translation.** Russian in-code commentary is being translated progressively;
help is welcome. Keep the argument, not just the words — these comments explain
why a decision was made, and a flattened translation loses the point of them.

**Anything that is plainly broken.** A wrong link, a stale number, a page that
does not render.

## What is not accepted

**A record without a resolvable source.** See above.

**A record for something that is not a technology.** Curated lists, surveys and
benchmarks are useful, but they are not points in the configuration space. A
survey may be worth adding as a *discovery source* instead; say so.

**A level set by hand because it feels right.** Levels are derived. If you think
a level is wrong, the fix is evidence, not the number.

**Prose written by a language model and submitted as your own reading of the
source.** The registry's value is that a person read the source. If you did not,
say so and we will treat it as a lead rather than a reading.

## Two ways in

### Open an issue

Best when you have found something and do not want to touch the repository. Use
the *Propose a registry record* or *Report an error* form; they ask for the few
fields we need and nothing else.

This is the low-effort path and it is genuinely fine. A good issue with a link
is more useful than a rushed pull request.

### Open a pull request

Best when you are comfortable editing JSON. A record is one file:

```
data/technologies/<id>.json
```

Prose lives separately, in both languages:

```
ui/src/i18n/ru/tech.json
ui/src/i18n/en/tech.json
```

Justifications for configuration values that differ from the base go in
`data/parse_notes.jsonl`, one line each, saying what the system does, why that
implies the value, and which part of the source says so.

Before opening the pull request:

```bash
make validate    # schema, referential integrity, provenance
make test        # the whole suite
make artifacts   # rebuild what the portal reads, and commit the result
```

The checks will tell you what is missing. They are strict on purpose: a record
that passes them is a record we can defend.

## House rules for prose

The registry is read by people who are not native speakers of either language,
and by people who know the field better than we do. Both matter.

- Terms are defined at first use. `Retrieval` is fine; unexplained jargon is not.
- No transliterated slang in Russian text, no undefined abbreviations.
- An em dash does not stand in for a verb; write the verb.
- Descriptions carry no counts. A number in a description is stale by the next
  weekly run, and search engines cache it for weeks after that.

These are enforced by tests, so you will find out quickly.

## Commits

Commit messages are in English and follow
[Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add PixelRAG to the registry
fix: correct A5 for ColBERT, the source says late interaction
docs: translate core/maturity.py commentary
```

Say **why** in the body, not just what. A commit that explains a decision is
worth more later than one that restates the diff.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

If something here is unclear, that is a defect in this page — open an issue and
say so.
