"""The file-based registry of RAG technologies.

The registry is the versioned files of the `data/` directory. This package holds
the models of the records and the read and write operations; everything else —
the collectors, the artefact build, the validation — works through it and knows
nothing of how the files are laid out.
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
