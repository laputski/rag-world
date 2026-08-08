"""Опубликованные артефакты не должны расходиться с реестром.

Артефакты производны от `data/`, но версионируются намеренно: статический
хостинг собирает только интерфейс и Python не запускает, поэтому без них
опубликованный портал остался бы без данных.

У версионирования производного есть цена — оно может устареть. Этот тест не даёт
устареть: он пересобирает артефакты во временный каталог и сравнивает с теми,
что лежат в репозитории. Расходятся — значит, кто-то правил `data/` и забыл
выполнить сборку.

Момент сборки при сравнении игнорируется: он меняется при каждом запуске и
содержания не несёт.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_artifacts import OUT_DIR, build  # noqa: E402

#: Поля, меняющиеся при каждой сборке и потому исключаемые из сравнения.
VOLATILE_KEYS = {"built_at"}

COMPARED = ["registry.json", "map.json", "changes.json", "stats.json"]


def _normalize(payload):
    """Убрать изменчивые поля на всех уровнях структуры."""
    if isinstance(payload, dict):
        return {
            key: _normalize(value)
            for key, value in payload.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    return payload


def test_published_artifacts_match_registry(tmp_path):
    build(out_dir=tmp_path)

    stale: list[str] = []
    for name in COMPARED:
        published = OUT_DIR / name
        assert published.exists(), (
            f"артефакт {name} отсутствует в репозитории; выполните `make artifacts`"
        )
        expected = _normalize(json.loads((tmp_path / name).read_text(encoding="utf-8")))
        actual = _normalize(json.loads(published.read_text(encoding="utf-8")))
        if expected != actual:
            stale.append(name)

    assert not stale, (
        "опубликованные артефакты разошлись с реестром: "
        + ", ".join(stale)
        + "; выполните `make artifacts` и зафиксируйте результат"
    )


def test_feed_is_published():
    """Лента хроники — единственный способ узнать об изменениях извне портала."""
    feed = OUT_DIR / "feed.xml"
    assert feed.exists(), "лента отсутствует; выполните `make artifacts`"
    text = feed.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml"), "лента не является XML-документом"
    assert "<channel>" in text
