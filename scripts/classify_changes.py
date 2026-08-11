#!/usr/bin/env python3
"""Классификация изменений реестра: применять само или показать человеку.

Раньше этот разбор жил внутри рабочего процесса, вписанный в YAML. Логика в
описании задания не проверяется тестами и не запускается локально, поэтому она
переехала сюда, а рабочий процесс остался обёрткой.

Правило исходит из принципа K6: изменение реестра всегда объяснимо, а те
изменения, которые трудно откатить или легко пропустить, проходят через
человека. Показу подлежат три случая:

* **понижение уровня** — оно означает, что прежнее утверждение было неверным
  либо технология деградировала; и то и другое требует проверки;
* **пересечение границы подтверждённости** (переход в L4 и выше) — дальше
  начинаются утверждения о независимом воспроизведении и промышленном
  применении, цена ошибки в которых выше;
* **свидетельство, введённое человеком** — если оно появилось в автоматическом
  проходе, значит кто-то правил файл ручных свидетельств, и это стоит увидеть.

Всё остальное применяется само. Пропускать через просмотр каждое изменение
нельзя: очередь переполнится, и просмотр выродится в формальность.

Использование::

    python3 scripts/classify_changes.py            # разобрать изменения в git
    python3 scripts/classify_changes.py --github   # вывод для рабочего процесса
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.registry import store  # noqa: E402

LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

#: Граница подтверждённости: с этого уровня начинаются утверждения о
#: независимом воспроизведении, и цена ошибки в них выше.
REVIEW_THRESHOLD = "L4"

#: Путь журнала уровней относительно корня репозитория. Берётся у хранилища, а
#: не пишется строкой: переезд журнала иначе оставил бы разбор смотреть в
#: пустоту, и шлюз молча решил бы, что изменений нет.
ROOT = Path(__file__).resolve().parent.parent
LEVELS_PATH = str(store.LEVELS_FILE.relative_to(ROOT))


class Undecidable(Exception):
    """Разобрать изменения не удалось.

    Отличается от «изменений нет» ровно тем, чем незнание отличается от
    знания. Шлюз, принявший одно за другое, пропускает в основную ветку
    понижения уровня и переходы через границу подтверждённости, и делает это
    молча.
    """


@dataclass
class Decision:
    """Итог разбора: нужен ли просмотр и почему."""

    needs_review: bool = False
    reasons: list[str] = field(default_factory=list)
    #: Сколько изменений уровня обнаружено всего.
    changes: int = 0

    def as_text(self) -> str:
        if not self.changes:
            return "изменений уровней нет"
        if not self.needs_review:
            return f"изменений {self.changes}, все применяются автоматически"
        return f"изменений {self.changes}, требуют просмотра: " + "; ".join(self.reasons)


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else -1


def classify(
    added: list[dict], previous_levels: dict[str, str] | None = None
) -> Decision:
    """Разобрать добавленные записи журнала уровней.

    `previous_levels` — уровень технологии до изменения. Отсутствие записи
    означает, что уровень вычислен впервые; повышением с пустого места это не
    считается и просмотра не требует.
    """
    previous_levels = previous_levels or {}
    decision = Decision(changes=len(added))

    for entry in added:
        tech = entry.get("technology_id", "?")
        level = entry.get("level", "")
        before = previous_levels.get(tech)

        if entry.get("evidence_basis") == "manual":
            decision.needs_review = True
            decision.reasons.append(f"{tech}: свидетельство введено человеком")
            continue

        if before is not None and _rank(level) < _rank(before):
            decision.needs_review = True
            decision.reasons.append(f"{tech}: понижение {before} → {level}")
            continue

        if _rank(level) >= _rank(REVIEW_THRESHOLD):
            decision.needs_review = True
            decision.reasons.append(
                f"{tech}: переход в {level}, граница подтверждённости"
            )

    return decision


def added_entries_from_git(repo: Path | None = None) -> list[dict]:
    """Записи, дописанные в журнал уровней и ещё не зафиксированные.

    Сравнение идёт с `HEAD`, а не с индексом. Разница решающая: `git diff` без
    указания показывает только непроиндексированное, поэтому любой `git add`,
    выполненный до шлюза, скрывал бы от него изменения целиком. Шлюз при этом
    не падал, а отвечал «изменений нет» и пропускал в основную ветку всё, включая
    понижения уровня.

    Всякая невозможность разобрать различия поднимает `Undecidable`. Прежде она
    оборачивалась пустым списком, а пустой список означает «изменений нет»:
    отсутствие репозитория, переезд журнала, оборванная строка и отказ git
    выглядели для шлюза одинаково безобидно.
    """
    # По умолчанию корень репозитория, а не текущий каталог: путь к журналу
    # задан относительно корня, и запуск из подкаталога иначе давал бы пустой
    # разбор вместо отказа.
    base = Path(repo) if repo is not None else ROOT

    # Отсутствие журнала git ошибкой не считает: пустой перечень путей для него
    # обычное дело, и `git diff` отвечает нулём и пустотой. Для шлюза это
    # неотличимо от «изменений нет», поэтому существование проверяется прямо.
    if not (base / LEVELS_PATH).exists():
        raise Undecidable(f"журнала уровней нет по пути {LEVELS_PATH}")

    result = subprocess.run(
        ["git", "diff", "HEAD", "--unified=0", "--", LEVELS_PATH],
        capture_output=True, text=True, cwd=base,
    )
    if result.returncode != 0:
        raise Undecidable(
            f"git не показал изменения {LEVELS_PATH}: "
            f"{result.stderr.strip()[:200] or 'код ' + str(result.returncode)}"
        )

    out: list[dict] = []
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            payload = line[1:].strip()
            if not payload:
                continue
            try:
                out.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise Undecidable(
                    f"строка журнала уровней не разбирается ({exc}); "
                    f"начало: {payload[:60]!r}"
                ) from exc
    return out


def previous_levels_before(added: list[dict]) -> dict[str, str]:
    """Уровни технологий до добавленных записей.

    Журнал упорядочен по времени, поэтому предыдущим считается последний
    уровень технологии среди записей, не входящих в добавленные.
    """
    added_keys = {
        (e.get("technology_id"), e.get("level"), e.get("computed_at")) for e in added
    }
    previous: dict[str, str] = {}
    for entry in store.load_levels():
        key = (entry.technology_id, entry.level, entry.computed_at.isoformat())
        if key in added_keys:
            continue
        previous[entry.technology_id] = entry.level
    return previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--github", action="store_true",
        help="вывести результат в формате переменных задания",
    )
    args = parser.parse_args()

    # Не смогли разобрать — значит, показываем человеку. Отказ закрытый: цена
    # лишнего просмотра равна одному щелчку, цена пропущенного понижения равна
    # неверному утверждению о технологии в основной ветке.
    #
    # Код возврата остаётся нулевым намеренно. Ненулевой остановил бы задание
    # целиком, и отметка о прогоне не попала бы в основную ветку, а от неё
    # зависит и признак активности репозитория, и дата последней проверки,
    # которую видит читатель.
    try:
        added = added_entries_from_git()
    except Undecidable as exc:
        sys.stderr.write(f"разобрать изменения не удалось: {exc}\n")
        if args.github:
            print("review=true")
            print("changes=0")
        else:
            print(f"разобрать изменения не удалось, нужен просмотр: {exc}")
        return 0

    decision = classify(added, previous_levels_before(added))

    if args.github:
        print(f"review={'true' if decision.needs_review else 'false'}")
        print(f"changes={decision.changes}")
    else:
        print(decision.as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
