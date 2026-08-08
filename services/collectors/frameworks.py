"""Сборщик присутствия во фреймворках.

Присутствие технологии в широко используемом фреймворке — одно из достаточных
условий уровня L4: оно означает, что реализацию сделал кто-то, кроме авторов, и
что ею пользуются не только в исходной статье. Без этого сборщика уровень L4
недостижим вовсе, каким бы известным ни был приём.

Опрашиваются каталоги интеграций трёх фреймворков через оглавления каталогов
репозитория. Поиск по коду не используется: он требует учётной записи и даёт
совпадения в комментариях и тестах, то есть ложные срабатывания там, где нужен
факт наличия интеграции.

Сопоставление строгое: имя файла или каталога должно совпасть с именем
технологии или её псевдонимом целиком после нормализации. Вхождение подстроки
дало бы «RAG» внутри доброй сотни имён.

Запросов немного: несколько на весь реестр, а не на каждую запись, — поэтому
опрос идёт в том же недельном проходе, что и остальное.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class FrameworkCatalog:
    """Фреймворк и каталоги, в которых лежат его интеграции."""

    name: str
    repo: str
    paths: tuple[str, ...]


#: Каталоги выбраны так, чтобы в них лежали именно интеграции, а не ядро.
CATALOGS: tuple[FrameworkCatalog, ...] = (
    # Раскладка репозитория менялась: интеграции переехали из libs/community в
    # libs/langchain/langchain_classic. Пути проверены обращением к оглавлению;
    # если они снова переедут, сборщик сообщит об этом кодом ответа, а не
    # промолчит — отсутствие свидетельств выглядело бы как их отсутствие в
    # действительности.
    FrameworkCatalog(
        "LangChain", "langchain-ai/langchain",
        (
            "libs/langchain/langchain_classic/retrievers",
            "libs/langchain/langchain_classic/vectorstores",
            "libs/partners",
        ),
    ),
    FrameworkCatalog(
        "LlamaIndex", "run-llama/llama_index",
        (
            "llama-index-integrations/retrievers",
            "llama-index-integrations/vector_stores",
            "llama-index-integrations/indices",
        ),
    ),
    FrameworkCatalog(
        "Haystack", "deepset-ai/haystack",
        ("haystack/components/retrievers", "haystack/components/rankers"),
    ),
)


def normalize(name: str) -> str:
    """Имя без разделителей и регистра: «Light-RAG» и «lightrag» совпадают."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


#: Слова, которые не могут служить ключом сопоставления, даже если записаны в
#: реестре как псевдоним. Они означают понятие, а не технологию, и совпадают с
#: чем угодно: у одного фреймворка есть компонент `memory` для истории
#: переписки, и запись «RAG as Memory» ошибочно получила по нему свидетельство
#: присутствия. Проверять надо название, а не общее слово.
GENERIC_TERMS: frozenset[str] = frozenset({
    "memory", "index", "indices", "graph", "search", "edge", "unified",
    "causal", "embodied", "federated", "streaming", "speculative", "modular",
    "agentic", "retrieval", "retriever", "reranker", "ranking", "vector",
    "store", "stores", "chunking", "generation", "adaptive", "corrective",
    "multimodal", "temporal", "spatial", "hybrid", "dense", "sparse",
})


def _strip_prefixes(stem: str) -> set[str]:
    """Варианты имени записи каталога без приставок фреймворка.

    Интеграции называются по-разному: `langchain-qdrant`, `llama-index-
    retrievers-bm25`, просто `bm25`. Сравнивать надо со всеми вариантами.
    """
    parts = re.split(r"[-_]", stem.lower())
    variants = {normalize(stem)}
    drop = {
        "langchain", "llama", "index", "llamaindex", "haystack",
        "retrievers", "retriever", "vector", "stores", "store", "indices",
        "community", "partners", "integrations", "py", "python",
    }
    kept = [p for p in parts if p and p not in drop]
    if kept:
        variants.add(normalize("".join(kept)))
        variants.add(normalize(kept[-1]))
    return {v for v in variants if v}


def fetch_catalog(
    catalog: FrameworkCatalog, *, http: HttpGetter, token: str | None = None
) -> tuple[set[str], list[str]]:
    """Нормализованные имена записей каталогов фреймворка и ошибки опроса."""
    names: set[str] = set()
    errors: list[str] = []
    headers = {"User-Agent": "rag-world/0.2", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for path in catalog.paths:
        url = f"{GITHUB_API}/repos/{catalog.repo}/contents/{path}"
        if not is_allowed_host(url):
            errors.append(f"{catalog.name}: домен вне allowlist")
            continue
        status, body = http.get(url, headers=headers, timeout=20)
        if status != 200:
            errors.append(f"{catalog.name}/{path}: код {status}")
            continue
        try:
            entries = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            errors.append(f"{catalog.name}/{path}: некорректный ответ")
            continue
        if not isinstance(entries, list):
            errors.append(f"{catalog.name}/{path}: неожиданный формат")
            continue
        for item in entries:
            raw = str(item.get("name", ""))
            stem = re.sub(r"\.(py|md|txt)$", "", raw)
            names |= _strip_prefixes(stem)
    return names, errors


def collect_frameworks(
    technologies: list,
    *,
    http: HttpGetter,
    token: str | None = None,
    today: date | None = None,
) -> tuple[list[RawEvidence], list[str]]:
    """Свидетельства о присутствии во фреймворках для всего реестра сразу.

    Принимает список записей, а не одну: оглавления читаются один раз на
    фреймворк, после чего сопоставление идёт в памяти.
    """
    today = today or date.today()
    evidence: list[RawEvidence] = []
    errors: list[str] = []

    catalogs: dict[str, set[str]] = {}
    for catalog in CATALOGS:
        names, catalog_errors = fetch_catalog(catalog, http=http, token=token)
        errors.extend(catalog_errors)
        if names:
            catalogs[catalog.name] = names

    for tech in technologies:
        wanted = {normalize(tech.name)} | {normalize(a) for a in tech.aliases}
        wanted |= {normalize(tech.id)}
        # Слишком короткие и общие формы отбрасываются: они совпадают со
        # множеством посторонних имён, а ложное свидетельство хуже отсутствия.
        wanted = {
            w for w in wanted if len(w) >= 4 and w not in GENERIC_TERMS
        }
        if not wanted:
            continue
        present = [name for name, entries in catalogs.items() if wanted & entries]
        if not present:
            continue
        evidence.append(RawEvidence(
            technology_id=tech.id,
            type="framework_presence",
            value=f"frameworks={', '.join(sorted(present))}",
            source=f"{GITHUB_API}/repos/"
                   + next(c.repo for c in CATALOGS if c.name == present[0]),
            fetched_at=today,
            obtained_by="auto",
            verified=False,
        ))
    return evidence, errors


def result_for(
    technologies: list, *, http: HttpGetter, token: str | None = None,
    today: date | None = None,
) -> CollectResult:
    """Обёртка в общий тип результата сбора."""
    evidence, errors = collect_frameworks(
        technologies, http=http, token=token, today=today
    )
    result = CollectResult(source_name="frameworks", technology_id="*")
    result.evidence.extend(evidence)
    result.errors.extend(errors)
    return result
