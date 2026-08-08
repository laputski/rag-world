"""Файловый реестр технологий RAG.

Реестр проекта — версионируемые файлы каталога `data/`. Этот пакет содержит
модели записей и операции чтения и записи; всё остальное (сборщики, сборка
артефактов, проверки) работает через него и не знает о раскладке файлов.
"""

from services.registry.store import (
    DATA_DIR,
    Evidence,
    LevelEntry,
    Link,
    MetricPoint,
    Technology,
    append_evidence,
    append_level,
    append_metrics,
    latest_level,
    load_evidence,
    load_levels,
    load_metrics,
    load_technologies,
    load_technology,
    save_technology,
)

__all__ = [
    "DATA_DIR",
    "Evidence",
    "LevelEntry",
    "Link",
    "MetricPoint",
    "Technology",
    "append_evidence",
    "append_level",
    "append_metrics",
    "latest_level",
    "load_evidence",
    "load_levels",
    "load_metrics",
    "load_technologies",
    "load_technology",
    "save_technology",
]
