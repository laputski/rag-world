#!/usr/bin/env python3
"""Проверка реестра: схема, ссылочная целостность, допустимость конфигураций.

Запускается в цепочке обновления и в проверках сборки. Падение означает, что
выпуск публиковать нельзя.

Что проверяется без сети:

* каждая запись читается схемой, идентификатор совпадает с именем файла и
  удовлетворяет соглашению;
* значения измерений существуют в схеме, а конфигурация допустима по
  ограничениям Φ;
* страты записи принадлежат A–G и не противоречат её конфигурации;
* свидетельства и записи журнала уровней ссылаются на существующие технологии;
* у каждого источника заполнен адрес, а состояние проверки согласовано с датой.

Разрешимость адресов требует сети и включается отдельно::

    python3 scripts/validate_data.py               # без сети
    python3 scripts/validate_data.py --check-links # с обращением к источникам

Такое разделение намеренно: проверки должны проходить при полной недоступности
внешних источников, иначе портал нельзя собрать в отсутствие сети.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dimensions_schema import ALL_VALUES, STRATA, validate  # noqa: E402
from services.registry import store  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9_]+$")
LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5", "L6"}


def _residual_vocabulary() -> dict[str, dict]:
    """Словарь механизмов остатка: код → запись словаря."""
    path = store.DATA_DIR / "residual_vocabulary.json"
    if not path.exists():
        return {}
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in payload.get("mechanisms", [])}


RESIDUAL_VOCABULARY = _residual_vocabulary()


def check_registry() -> list[str]:
    """Проверки, не требующие сети. Возвращает список нарушений."""
    problems: list[str] = []

    try:
        technologies = store.load_technologies()
    except Exception as exc:
        return [f"реестр не читается схемой: {exc}"]

    if not technologies:
        return ["реестр пуст: нет ни одной записи в data/technologies/"]

    known: set[str] = set()
    for tech in technologies:
        where = f"technologies/{tech.id}.json"

        if not ID_RE.match(tech.id):
            problems.append(
                f"{where}: идентификатор {tech.id!r} нарушает соглашение "
                "(строчные латинские буквы, цифры и подчёркивание)"
            )
        if tech.id in known:
            problems.append(f"{where}: повторный идентификатор {tech.id!r}")
        known.add(tech.id)

        if not tech.name.strip():
            problems.append(f"{where}: пустое имя")

        for group in tech.groups:
            if group not in STRATA:
                problems.append(f"{where}: неизвестная страта {group!r}")

        for code, value in tech.configuration.items():
            if code not in ALL_VALUES:
                problems.append(f"{where}: неизвестное измерение {code!r}")
            elif value not in ALL_VALUES[code]:
                problems.append(
                    f"{where}: измерение {code} имеет значение {value!r}, "
                    f"которого нет в схеме"
                )
        if tech.configuration:
            for error in validate(tech.configuration):
                problems.append(f"{where}: конфигурация недопустима: {error}")

        # Остаток ссылается на словарь кодом. Свободный текст отклоняется:
        # один и тот же механизм, названный по-разному в двух записях, не
        # сойдётся при подсчёте, и очередь остатков покажет десять редких
        # механизмов вместо одного частого.
        for mechanism in tech.residual:
            if mechanism not in RESIDUAL_VOCABULARY:
                problems.append(
                    f"{where}: остаток {mechanism!r} отсутствует в словаре "
                    f"data/residual_vocabulary.json"
                )

        if tech.configuration_reviewed and not tech.configuration:
            problems.append(
                f"{where}: конфигурация помечена разобранной, но пуста"
            )

        for link in tech.links:
            if not link.url.strip():
                problems.append(f"{where}: источник без адреса")
            if link.status == "verified" and link.verified_at is None:
                problems.append(
                    f"{where}: источник {link.url} помечен проверенным, "
                    "но дата проверки не указана"
                )

    for item in store.load_evidence():
        if item.technology_id not in known:
            problems.append(
                f"evidence: свидетельство ссылается на неизвестную технологию "
                f"{item.technology_id!r}"
            )
        if not item.source.strip():
            problems.append(
                f"evidence: свидетельство {item.type} у {item.technology_id} "
                "не имеет источника"
            )

    for entry in store.load_levels():
        if entry.technology_id not in known:
            problems.append(
                f"levels: запись ссылается на неизвестную технологию "
                f"{entry.technology_id!r}"
            )
        if entry.level not in LEVELS:
            problems.append(
                f"levels: у {entry.technology_id} недопустимый уровень {entry.level!r}"
            )
        if not 0.0 <= entry.confidence <= 1.0:
            problems.append(
                f"levels: у {entry.technology_id} уверенность {entry.confidence} "
                "вне отрезка [0, 1]"
            )

    for point in store.load_metrics():
        if point.technology_id not in known:
            problems.append(
                f"metrics: показатель ссылается на неизвестную технологию "
                f"{point.technology_id!r}"
            )
        if not point.source.strip():
            problems.append(
                f"metrics: показатель {point.metric} у {point.technology_id} "
                "не имеет источника"
            )

    return problems


def check_links() -> list[str]:
    """Разрешимость адресов источников. Требует сети."""
    from services.collectors.transport import RequestsTransport

    transport = RequestsTransport()
    problems: list[str] = []
    seen: set[str] = set()
    for tech in store.load_technologies():
        for link in tech.links:
            if link.url in seen:
                continue
            seen.add(link.url)
            try:
                status, _ = transport.get(link.url)
            except Exception as exc:
                problems.append(f"{tech.id}: {link.url} недоступен ({exc})")
                continue
            if status >= 400:
                problems.append(f"{tech.id}: {link.url} отвечает кодом {status}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-links", action="store_true",
        help="дополнительно проверить разрешимость адресов источников (нужна сеть)",
    )
    args = parser.parse_args()

    problems = check_registry()
    if args.check_links:
        problems += check_links()

    if problems:
        sys.stderr.write(f"Проверка данных не пройдена: нарушений {len(problems)}\n")
        for problem in problems:
            sys.stderr.write(f"  {problem}\n")
        return 1

    technologies = store.load_technologies()
    evidence = store.load_evidence()
    levels = store.load_levels()
    print(
        f"Проверка данных пройдена: технологий {len(technologies)}, "
        f"свидетельств {len(evidence)}, записей журнала уровней {len(levels)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
