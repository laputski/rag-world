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
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "ui" / "public" / "data"
RELEASES = ARTIFACTS / "releases"

#: Что входит в снимок. Лента не входит: она о новостях, а не о состоянии.
SNAPSHOT_FILES = ("registry.json", "map.json", "stats.json", "residuals.json")

#: Поля, меняющиеся при каждой сборке и потому не значащие расхождения.
VOLATILE_KEYS = {"built_at"}


def artifacts_dir() -> Path:
    """Каталог артефактов. Читается заново, чтобы тесты могли его подменить."""
    return ARTIFACTS


def releases_dir() -> Path:
    return RELEASES


def _normalize(payload):
    if isinstance(payload, dict):
        return {
            key: _normalize(value)
            for key, value in payload.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    return payload


def readiness() -> list[str]:
    """Причины, по которым выпускать нельзя. Пусто — можно.

    Выпуск фиксирует состояние навсегда, поэтому проверяется он строже
    обычного прохода. Проверок три, и каждая закрывает случай, доказанный на
    этом же коде.

    Первая: данные обязаны быть исправны. Выпуск не звал проверку вовсе, и
    зафиксировать испорченный реестр навсегда ему ничто не мешало.

    Вторая: артефакты обязаны быть собраны из нынешних данных. Числа выпуска
    берутся из `data/`, а файлы копируются из `ui/public/data/`, и сверки между
    ними не было. Расхождение получалось не теоретическое: снимок утверждал
    шестьдесят две технологии, а лежала в нём одна.

    Третья: все файлы снимка обязаны существовать. Отсутствующий копировался
    молча, и выпуск обещал в своём перечне файл, которого в нём нет.
    """
    import build_artifacts
    import validate_data

    problems = [f"данные не проходят проверку: {p}" for p in
                validate_data.check_registry()]

    missing = [name for name in SNAPSHOT_FILES
               if not (artifacts_dir() / name).exists()]
    if missing:
        problems.append(
            f"артефакты не собраны: нет {', '.join(missing)}; "
            "выполните `make artifacts`"
        )
        return problems

    with tempfile.TemporaryDirectory() as tmp:
        build_artifacts.build(out_dir=Path(tmp))
        for name in SNAPSHOT_FILES:
            fresh = Path(tmp) / name
            if not fresh.exists():
                continue
            expected = _normalize(json.loads(fresh.read_text(encoding="utf-8")))
            actual = _normalize(
                json.loads((artifacts_dir() / name).read_text(encoding="utf-8"))
            )
            if expected != actual:
                problems.append(
                    f"артефакт {name} собран не из нынешних данных; "
                    "выполните `make artifacts` и зафиксируйте результат"
                )
    return problems


def releases_index() -> list[dict]:
    """Выпущенные снимки, свежие впереди."""
    path = releases_dir() / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("releases", [])


def is_complete(tag: str) -> bool:
    """Выпущен ли снимок целиком.

    Каталог выпуска существовал и после прерывания на середине, а проверялось
    именно существование. Прерванный выпуск навсегда оставался пустым: повтор
    видел каталог, сообщал «уже существует» и уходил, а `publish` отказался бы
    переписывать. Целостность теперь спрашивается у содержимого.
    """
    target = releases_dir() / tag
    if not (target / "release.json").exists():
        return False
    if any(not (target / name).exists() for name in SNAPSHOT_FILES):
        return False
    if not (releases_dir() / f"rag-world-{tag}.zip").exists():
        return False
    if not (releases_dir() / f"{tag}-deposit.json").exists():
        return False
    return any(item.get("tag") == tag for item in releases_index())


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
    """Записать снимок. Существующий выпуск не переписывается никогда.

    Снимок собирается рядом и переносится в место назначения одним движением.
    Прерывание на середине оставляет черновик, а не полувыпуск: каталог под
    меткой появляется уже целым. Это важнее обычного, потому что повторить
    выпуск нельзя — на него уже могла лечь ссылка.
    """
    target = releases_dir() / meta["tag"]
    if target.exists():
        raise FileExistsError(
            f"выпуск {meta['tag']} уже существует: {target}. Выпуск фиксирует "
            "состояние навсегда, и переписывать его нельзя: ссылка на него уже "
            "могла попасть в чужую работу."
        )

    missing = [name for name in SNAPSHOT_FILES
               if not (artifacts_dir() / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"снимок неполон: нет {', '.join(missing)}. Выпуск перечисляет свои "
            "файлы, и обещать в нём отсутствующий значит дать ссылку в никуда."
        )

    releases_dir().mkdir(parents=True, exist_ok=True)
    draft = Path(tempfile.mkdtemp(prefix=f".{meta['tag']}-", dir=releases_dir()))
    try:
        for name in SNAPSHOT_FILES:
            shutil.copy2(artifacts_dir() / name, draft / name)
        (draft / "release.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(draft, target)
    except BaseException:
        shutil.rmtree(draft, ignore_errors=True)
        raise

    index = [r for r in releases_index() if r["tag"] != meta["tag"]] + [meta]
    index.sort(key=lambda r: r["tag"], reverse=True)
    (releases_dir() / "index.json").write_text(
        json.dumps({"releases": index}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
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
    target = releases_dir() / meta["tag"]
    archive = shutil.make_archive(
        str(releases_dir() / f"rag-world-{meta['tag']}"), "zip", root_dir=target
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
    (releases_dir() / f"{meta['tag']}-deposit.json").write_text(
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

    # Проверка идёт и на пробном прогоне: узнать, что выпускать нельзя, лучше
    # до выпуска, а не вместо него.
    problems = readiness()
    if problems:
        sys.stderr.write(f"выпускать нельзя: препятствий {len(problems)}\n")
        for problem in problems:
            sys.stderr.write(f"  {problem}\n")
        return 1

    if dry_run:
        print("пробный прогон: препятствий нет, записано ничего не будет")
        return 0

    if is_complete(meta["tag"]):
        print(f"выпуск {meta['tag']} уже существует целиком, повторный не пишется")
        return 0

    path = releases_dir() / meta["tag"]
    if path.exists():
        # Каталог есть, а выпуска нет: прежде такое состояние сообщало «уже
        # существует» и оставалось навсегда.
        sys.stderr.write(
            f"выпуск {meta['tag']} записан не целиком: каталог {path} есть, а "
            "снимка, архива, описания или записи в перечне нет. Уберите каталог "
            "и выпустите заново, если на выпуск ещё никто не ссылался.\n"
        )
        return 1

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
