# Cutting a release and depositing it for a DOI

A release is the only thing here that cannot be taken back. Everything else in
the project can be recomputed from the sources; a release is a promise that a
particular set of numbers will still be there in five years, and somebody else's
paper may come to depend on it.

This document is the procedure. It exists because the procedure is performed
rarely, and a step recalled from memory a few months later is the step that goes
wrong.

## 1. Cut the release

```bash
make release
```

The target rebuilds the artefacts first and then writes, under
`ui/public/data/releases/<date>/`, a snapshot of `registry.json`, `map.json`,
`stats.json` and `residuals.json`, a `release.json` with the counts, an entry in
the release index, an archive `rag-world-<date>.zip`, and a deposit description
`<date>-deposit.json`.

It refuses, rather than producing a doubtful snapshot, when the data does not
pass validation, when the artefacts were not built from the current `data/`, or
when a file the snapshot promises is missing. A release of that date that
already exists is never overwritten: a link to it may already be in somebody
else's work.

To see what would happen without writing anything:

```bash
make release-dry
```

Commit the result. The snapshot is data, and data lives in the repository.

## 2. Deposit it on Zenodo

Zenodo issues the persistent identifier. Two routes exist and they are not
interchangeable.

**Route A, the archive of the data — use this one.** Upload
`rag-world-<date>.zip` by hand as a new dataset. What gets a DOI is then the
registry snapshot, which is the object `CITATION.cff` describes and the object
people cite.

1. Sign in at [zenodo.org](https://zenodo.org) and choose New upload.
2. Attach `ui/public/data/releases/rag-world-<date>.zip`.
3. Fill the form from `<date>-deposit.json`, which carries every field already
   written out: title, description with the counts, upload type `dataset`,
   creators, publication date, version, language, keywords, access right, and
   the licence CC BY 4.0. Copy them across rather than retyping — the numbers in
   the description are the content, and a number retyped by hand is a number
   eventually mistyped.
4. Reserve the DOI before publishing if you want to name it inside the deposited
   files. Otherwise publish and take the DOI afterwards.

**Route B, the GitHub integration — not for this.** Zenodo can watch the
repository and archive it on every GitHub Release. What it archives is the
source tree at a tag, which is the code and not the registry snapshot, and the
code is Apache-2.0 while the data is CC BY 4.0. Enabling it would mint DOIs for
an object nobody in this project asks people to cite.

The integration is switched on for this repository, and that is harmless as long
as no GitHub Release is cut: it archives on a release and on nothing else. Should
one ever be cut, the record it produces has to say it archives the software,
separately from the dataset.

## 3. After the DOI exists

Zenodo issues two identifiers, and the difference decides where each goes. The
**version DOI** points at one deposit and never moves: it is what a paper should
cite, because a claim about the data is a claim about one state of it. The
**concept DOI** always resolves to the newest version, and it is what belongs
wherever "the current registry" is meant.

Record the **version DOI** in the release index, on the entry for that release:

```json
{ "tag": "2026-08-14", "doi": "10.5281/zenodo.21943979", ... }
```

It is added by hand, because the identifier exists only after the deposit and
`make_release.py` cannot know it at the moment a release is cut. Existing entries
survive later releases untouched, so it stays. From there every citation format
picks it up: the About page shows it in BibTeX, in GOST and in the plain English
form, beside the address rather than instead of it — the address resolves for a
reader with no library behind them.

Record the **concept DOI**, which always resolves to the newest release, in two
places:

- `CITATION.cff` as `doi:`, so that GitHub's own "Cite this repository" widget
  offers it;
- `README.md` as a badge beside the licence badges.

Until a release has been deposited its citations point at
`https://ragworld.org/data/releases/<date>/registry.json`, which is stable but
depends on the hosting outliving the citation. That dependency is what an
identifier removes, and it is the reason to do this at all.
