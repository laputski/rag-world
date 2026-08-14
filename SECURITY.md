# Security policy

## Scope

RAG World is a static site over open data. It has no accounts, no user input,
and no server-side code: the portal reads pre-built JSON files and nothing else.
The realistic risk surface is therefore small, and it is mostly about data.

## Reporting

Report anything you find through
[GitHub's private vulnerability reporting](https://github.com/laputski/rag-world/security/advisories/new).
Please do not open a public issue for a security problem.

Expect a first reply within a week. This is a one-person project, so an
acknowledgement may arrive before an analysis does.

## What we consider a security problem

- A way to get content into the published artefacts without it passing
  validation — the collectors read third-party sources, and content from a
  source is data, never an instruction.
- A supply-chain problem in the build or in the scheduled run.
- Anything that lets a third party alter what the portal publishes.

## What we do not

- A wrong maturity level or a misread configuration value. Those are data
  defects; please open a normal issue, they are welcome.
- A broken or unreachable source link. The weekly run reports those already.
