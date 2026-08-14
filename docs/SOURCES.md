<!-- GENERATED from services/collectors/ by `python3 scripts/build_sources.py`. Do not edit by hand: an edit would be lost. -->

# The resources polled

These are the only places the portal goes. The list is generated from the code of the collectors, so it cannot drift from it.

No key and no account is required anywhere. A hosting token is used when one is present, and only for the sake of a higher rate limit.

## Entry points

| Resource | Address | What is taken |
| --- | --- | --- |
| Preprints | `http://export.arxiv.org/api/query` | Confirms that a preprint exists and compares its title with the one claimed. Yields the level L1. |
| The open index of works | `https://api.openalex.org` | The publication venue, whether it was peer-reviewed, the citation count and the citation velocity. Yields the level L2 by the scholarly route, and all the attention shown on the map. |
| Repositories | `https://api.github.com` | The licence, the date of the last edit, whether releases exist. Yields the level L3. The same address serves the integration listings below. |
| The package index | `https://pypi.org/pypi` | That a package exists, and its version. It is asked only where the package name was written down by a person: guessing is inadmissible, because somebody else's package with a similar name would yield false evidence. |
| A curated topic list | `https://github.com/DEEP-PolyU/Awesome-GraphRAG` | A second route of discovery, built on a different principle from the catalogue. The catalogue knows about a work what whoever uploaded it claimed, whereas inclusion in a list is the decision of a person who works in the subject. Only the identifiers of works are taken from the markup; what is known about them comes from the preprint archive, because a list is written by hand and its wording cannot be trusted. |
| The works-and-code catalogue | `https://paperswithcode.co/api/v1` | The publication venue from a second source: while it came from the open index alone, an error there was covered by nothing. The same catalogue gives a feed of works under the method tag `rag` for discovering new ones. It is run by the community after paperswithcode.com closed. |
| Package downloads | `https://pypistats.org/api/packages` | The number of downloads in a month. Together with presence in a framework it yields the level L4. |

## Integration folders

Directory listings are read rather than code search: a technology is present in a framework when a folder of its own exists. The paths change along with the layout of somebody else's repository, which makes this the most brittle part of the list.

| Framework | Repository | Folders |
| --- | --- | --- |
| LangChain | `langchain-ai/langchain` | `libs/langchain/langchain_classic/retrievers`, `libs/langchain/langchain_classic/vectorstores`, `libs/partners` |
| LlamaIndex | `run-llama/llama_index` | `llama-index-integrations/retrievers`, `llama-index-integrations/vector_stores`, `llama-index-integrations/indices` |
| Haystack | `deepset-ai/haystack` | `haystack/components/retrievers`, `haystack/components/rankers` |

## Politeness

The pause between two requests to one host. The values come from what the resources ask for, not from convenience.

| Host | Pause, s |
| --- | --- |
| `api.github.com` | 1.0 |
| `api.openalex.org` | 1.0 |
| `arxiv.org` | 4.0 |
| `export.arxiv.org` | 4.0 |
| `paperswithcode.co` | 1.0 |
| `pypi.org` | 0.2 |
| any other | 0.5 |

The portal introduces itself as `rag-world/0.2 (registry; +https://ragworld.org)`. The open index of works keeps a separate request pool for those who give a contact address: it is taken from the environment variable `OPENALEX_MAILTO`, and without it a pass runs slower and risks a refusal on rate.

Retries after a refusal on rate: 3.

## What the portal does not do by itself

It does not create records. Discovery asks the catalogue under the method tag and appends what it finds to the candidate queue, and the verdict on each is a person's: a rule telling a new architecture from an application of an existing one errs, and the price of the error is a registry record about something that does not exist. The queue is shown on the Gaps page.
