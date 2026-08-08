"""Файловый реестр технологий RAG.

Реестр проекта — версионируемые файлы каталога `data/`. Этот пакет содержит
модели записей и операции чтения и записи; всё остальное (сборщики, сборка
артефактов, проверки) работает через него и не знает о раскладке файлов.
"""

from services.registry.store import (
    COLLECTION_LOG,
    DATA_DIR,
    CollectionRun,
    Evidence,
    LevelEntry,
    Link,
    MetricPoint,
    Technology,
    append_evidence,
    append_level,
    append_metrics,
    append_run,
    latest_level,
    latest_run,
    load_evidence,
    load_levels,
    load_metrics,
    load_runs,
    load_technologies,
    load_technology,
    save_technology,
)

__all__ = [
    "COLLECTION_LOG",
    "DATA_DIR",
    "CollectionRun",
    "Evidence",
    "LevelEntry",
    "Link",
    "MetricPoint",
    "Technology",
    "append_evidence",
    "append_level",
    "append_metrics",
    "append_run",
    "latest_level",
    "latest_run",
    "load_evidence",
    "load_levels",
    "load_metrics",
    "load_runs",
    "load_technologies",
    "load_technology",
    "save_technology",
]
