#!/usr/bin/env python3
"""Выпуск реестра: снимок состояния, на который можно сослаться.

Учёные не ссылаются на сайты. Сайт меняется, и ссылка перестаёт подтверждать
то, ради чего дана: читатель открывает её и видит другое. Ссылаются на то, у
чего есть версия.

Выпуск — датированный снимок артефактов. Он кладётся рядом с ними под своей
меткой и **никогда не переписывается**: в этом весь смысл. Ссылка вида
`/data/releases/2026-08-10/registry.json` через год отдаёт то же, что сегодня,
даже если реестр за это время вырос вдвое.

Отдельного идентификатора у записи нет и не будет. Запись меняется, и
постоянный идентификатор у изменяющегося объекта вводит в заблуждение сильнее,
чем его отсутствие: ссылка выглядит надёжной, а указывает на движущуюся цель.
Ссылаться следует на запись **в выпуске**.

Использование::

    python3 scripts/make_release.py            # выпустить снимок на сегодня
    python3 scripts/make_release.py --dry-run  # показать, что попадёт в выпуск
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "ui" / "public" / "data"
RELEASES = ARTIFACTS / "releases"

#: Что входит в снимок. Лента не входит: она о новостях, а не о состоянии.
SNAPSHOT_FILES = ("registry.json", "map.json", "stats.json", "residuals.json")


def releases_index() -> list[dict]:
    """Выпущенные снимки, свежие впереди."""
    path = RELEASES / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("releases", [])


def build(tag: str | None = None, today: date | None = None) -> dict:
    """Сведения о выпуске: метка, дата и что в нём зафиксировано."""
    today = today or date.today()
    tag = tag or today.isoformat()
    technologies = store.load_technologies()
    return {
        "tag": tag,
        "released_at": today.isoformat(),
        "technologies": len(technologies),
        "evidence": len(store.load_evidence()),
        "with_level": sum(1 for t in technologies if store.latest_level(t.id)),
        "reviewed": sum(1 for t in technologies if t.configuration_reviewed),
        "files": list(SNAPSHOT_FILES),
    }


def publish(meta: dict) -> Path:
    """Записать снимок. Существующий выпуск не переписывается никогда."""
    target = RELEASES / meta["tag"]
    if target.exists():
        raise FileExistsError(
            f"выпуск {meta['tag']} уже существует: {target}. Выпуск фиксирует "
            "состояние навсегда, и переписывать его нельзя — ссылка на него уже "
            "могла попасть в чужую работу."
        )
    target.mkdir(parents=True)
    for name in SNAPSHOT_FILES:
        source = ARTIFACTS / name
        if source.exists():
            shutil.copy2(source, target / name)
    (target / "release.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    index = [r for r in releases_index() if r["tag"] != meta["tag"]] + [meta]
    index.sort(key=lambda r: r["tag"], reverse=True)
    (RELEASES / "index.json").write_text(
        json.dumps({"releases": index}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def bundle(meta: dict) -> Path:
    """Собрать архив выпуска и описание для внешнего архива публикаций.

    Цифровой идентификатор нужен снимку данных, а не исходному коду: ссылаются
    на состояние реестра, а не на то, каким кодом оно получено. Поэтому
    закрытость репозитория делу не мешает — внешний архив принимает файлы
    напрямую, без связи с системой контроля версий.

    Описание пишется рядом в готовом виде: заполнять его руками при каждом
    выпуске значит однажды ошибиться в числах, а числа здесь и есть содержание.
    """
    target = RELEASES / meta["tag"]
    archive = shutil.make_archive(
        str(RELEASES / f"rag-world-{meta['tag']}"), "zip", root_dir=target
    )

    description = (
        f"Снимок реестра технологий Retrieval-Augmented Generation на "
        f"{meta['released_at']}. Зафиксировано технологий: {meta['technologies']}, "
        f"свидетельств: {meta['evidence']}; уровень зрелости вычислен у "
        f"{meta['with_level']}, конфигурация выведена из первоисточников у "
        f"{meta['reviewed']}. "
        "Уровень вычисляется детерминированным правилом из собранных "
        "свидетельств, без языковой модели. Конфигурация каждой записи выведена "
        "из раздела метода первоисточника, и обоснование каждого значения "
        "хранится вместе с данными."
    )
    (RELEASES / f"{meta['tag']}-deposit.json").write_text(
        json.dumps({
            "metadata": {
                "title": (
                    "RAG World: реестр технологий Retrieval-Augmented Generation, "
                    f"выпуск {meta['tag']}"
                ),
                "upload_type": "dataset",
                "description": description,
                "creators": [{"name": "Laputski, Alexander"}],
                "publication_date": meta["released_at"],
                "version": meta["tag"],
                "language": "rus",
                "keywords": [
                    "retrieval-augmented generation", "RAG", "feature model",
                    "technology readiness", "configuration space",
                ],
                "access_right": "open",
                "license": "cc-by-4.0",
            },
            "files": [Path(archive).name],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return Path(archive)


def run(*, dry_run: bool = False, today: date | None = None) -> int:
    meta = build(today=today)
    print(
        f"выпуск {meta['tag']}: технологий {meta['technologies']}, "
        f"свидетельств {meta['evidence']}, с уровнем {meta['with_level']}, "
        f"разобрано {meta['reviewed']}"
    )
    if dry_run:
        return 0
    path = RELEASES / meta["tag"]
    if path.exists():
        print(f"выпуск {meta['tag']} уже существует, повторный не пишется")
        return 0
    print(f"снимок записан: {publish(meta)}")
    archive = bundle(meta)
    print(
        f"пакет для внешнего архива: {archive.name}, описание "
        f"{meta['tag']}-deposit.json"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="показать, не записывая")
    args = parser.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
