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
an object nobody in this project asks people to cite. If it is ever enabled, it
should be described as archiving the software, separately from the dataset.

Zenodo issues two identifiers, and the difference matters when citing. The
**version DOI** points at one deposit and never moves: this is what a paper
should cite, because a claim about the data is a claim about one state of it.
The **concept DOI** always resolves to the newest version and is what belongs in
a README, where "the current registry" is meant.

## 3. After the DOI exists

Three places name it, and all three should be updated in the same commit:

- `CITATION.cff` — add `doi:` with the concept DOI, so that GitHub's own "Cite
  this repository" widget offers it;
- `README.md` — a DOI badge beside the licence badges;
- the About page of the portal — the citation formats are built in
  `ui/src/citation.ts`, which currently produces a URL to the release. A DOI
  belongs in the same entry, not instead of the URL: the DOI resolves for a
  reader with a library, the URL for everyone else.

Until a DOI exists, the citation formats point at
`https://ragworld.org/data/releases/<date>/registry.json`, which is stable but
depends on the hosting outliving the citation. That is precisely the dependency
a DOI removes, and it is the reason to do this at all.
