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


def test_residual_codes_are_resolved_to_wording():
    """Данные хранят код механизма, читателю показывается формулировка.

    Разделение существует ради перевода: английская локализация меняет словарь,
    а не пятьдесят четыре записи реестра. Но если подстановка сломается,
    карточка покажет читателю `synonymy_edges`, и заметить это можно будет
    только глазами.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    vocabulary = json.loads(
        (root / "data" / "residual_vocabulary.json").read_text(encoding="utf-8")
    )
    codes = {m["id"] for m in vocabulary["mechanisms"]}
    wording = {m["ru"] for m in vocabulary["mechanisms"]}

    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    seen = 0
    for row in published["technologies"]:
        for item in row.get("residual", []):
            seen += 1
            assert item not in codes, f"в артефакт попал код вместо формулировки: {item}"
            assert item in wording, f"формулировка вне словаря: {item!r}"
    assert seen > 0, "ни одного остатка в артефакте — проверка ничего не проверила"


def test_marked_dimensions_survive_into_the_artifact():
    """Пометки бесполезны, если не доходят до читателя.

    Они существуют, чтобы значение не читалось как утверждение, которым оно не
    является. Потеря их при сборке возвращает ровно ту неправду, ради которой
    поля заводились.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    rows = {row["id"]: row for row in published["technologies"]}

    marked = [
        r for r in rows.values()
        if r.get("configuration_variable") or r.get("configuration_inapplicable")
    ]
    assert marked, "ни одной помеченной записи — проверка ничего не проверяет"

    for row in marked:
        for code in row.get("configuration_inapplicable", []):
            assert code not in row["configuration"], (
                f"{row['id']}: неприменимое измерение {code} несёт значение"
            )
        for code in row.get("configuration_variable", []):
            assert code in row["configuration"], (
                f"{row['id']}: переменное измерение {code} без значения"
            )
