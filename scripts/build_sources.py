#!/usr/bin/env python3
"""Перечень опрашиваемых ресурсов, порождённый из кода сборщиков.

Такого перечня не было, и узнать, куда портал ходит, можно было только чтением
шести модулей. Написанный руками он разошёлся бы с кодом при первом же переезде
чужого каталога, а переезд уже случался: интеграции LangChain переехали из
`libs/community` в `libs/langchain/langchain_classic`.

Поэтому файл порождается: адреса, пути и паузы берутся у самих сборщиков, а
руками написано только назначение каждого ресурса. Расхождение невозможно по
построению, а сторож `tests/architecture/test_sources_in_sync.py` не даёт
забыть пересборку.

Использование::

    python3 scripts/build_sources.py            # перезаписать docs/SOURCES.md
    python3 scripts/build_sources.py --check    # только сверить, ничего не писать
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.collectors import frameworks, transport  # noqa: E402
from services.collectors.arxiv import ARXIV_API  # noqa: E402
from services.collectors.github import GITHUB_API  # noqa: E402
from services.collectors.openalex import OPENALEX_API, OPENALEX_MAILTO_ENV  # noqa: E402
from services.collectors.paperswithcode import PWC_API, RAG_METHOD  # noqa: E402
from services.collectors.pypi import PYPI_API, STATS_API  # noqa: E402

OUT = ROOT / "docs" / "SOURCES.md"

#: Назначение ресурса: зачем портал туда ходит и что оттуда берёт. Прозу нельзя
#: вывести из кода, поэтому она здесь; адреса, наоборот, только из кода.
PURPOSE = {
    ARXIV_API: (
        "Препринты",
        "Подтверждает существование препринта и сверяет заголовок с заявленным. "
        "Даёт уровень L1.",
    ),
    OPENALEX_API: (
        "Открытый индекс работ",
        "Площадка публикации, признак рецензирования, число цитирований и "
        "скорость цитирования. Даёт уровень L2 научным путём и всё внимание на "
        "карте.",
    ),
    GITHUB_API: (
        "Репозитории",
        "Лицензия, дата последней правки, наличие выпусков. Даёт уровень L3. "
        "Тем же адресом читаются оглавления каталогов интеграций (ниже).",
    ),
    PYPI_API: (
        "Индекс пакетов",
        "Существование пакета и его версия. Опрашивается только там, где имя "
        "пакета записано человеком: угадывать нельзя, чужой пакет с похожим "
        "именем даст ложное свидетельство.",
    ),
    PWC_API: (
        "Каталог работ и кода",
        "Площадка публикации вторым источником: пока она приходила только из "
        "открытого индекса, его ошибка ничем не перекрывалась. Оттуда же лента "
        f"работ под меткой метода `{RAG_METHOD}` для обнаружения новых. "
        "Каталог ведёт сообщество при Hugging Face после закрытия "
        "paperswithcode.com.",
    ),
    STATS_API: (
        "Загрузки пакетов",
        "Число загрузок за месяц. Вместе с присутствием во фреймворках даёт "
        "уровень L4.",
    ),
}


def render() -> str:
    lines = [
        "<!-- ПОРОЖДЕНО из services/collectors/ командой "
        "`python3 scripts/build_sources.py`. Не править вручную: правка "
        "потеряется. -->",
        "",
        "# Опрашиваемые ресурсы",
        "",
        "Портал ходит только сюда. Список порождается из кода сборщиков, "
        "поэтому разойтись с ним не может.",
        "",
        "Ключей и учётных записей не требуется нигде. Токен площадки "
        "используется, если он есть, и только ради более высоких пределов "
        "частоты обращений.",
        "",
        "## Точки входа",
        "",
        "| Ресурс | Адрес | Что берётся |",
        "| --- | --- | --- |",
    ]
    for url, (name, purpose) in PURPOSE.items():
        lines.append(f"| {name} | `{url}` | {purpose} |")

    lines += [
        "",
        "## Каталоги интеграций",
        "",
        "Читаются оглавления каталогов, а не поиск по коду: присутствие "
        "технологии во фреймворке проверяется наличием её каталога. Пути "
        "меняются вместе с раскладкой чужих репозиториев, и это самая хрупкая "
        "часть перечня.",
        "",
        "| Фреймворк | Репозиторий | Каталоги |",
        "| --- | --- | --- |",
    ]
    for catalog in frameworks.CATALOGS:
        paths = ", ".join(f"`{p}`" for p in catalog.paths)
        lines.append(f"| {catalog.name} | `{catalog.repo}` | {paths} |")

    lines += [
        "",
        "## Вежливость",
        "",
        "Пауза между обращениями к одному узлу. Значения взяты из требований "
        "самих ресурсов, а не из удобства.",
        "",
        "| Узел | Пауза, с |",
        "| --- | --- |",
    ]
    for host, delay in sorted(transport.HOST_DELAYS.items()):
        lines.append(f"| `{host}` | {delay} |")
    lines += [
        f"| прочие | {transport.DEFAULT_DELAY} |",
        "",
        f"Портал представляется строкой `{transport.DEFAULT_USER_AGENT}`. "
        f"Открытый индекс работ держит отдельный поток для тех, кто назвался "
        f"почтой для связи: адрес берётся из переменной окружения "
        f"`{OPENALEX_MAILTO_ENV}`, без неё прогон идёт медленнее и рискует "
        f"упереться в отказ по частоте.",
        "",
        f"Повторов при отказе по частоте: {transport.RETRIES_ON_RATE_LIMIT}.",
        "",
        "## Чего портал не делает сам",
        "",
        "Автоматического заведения записей. Обнаружение опрашивает каталог по "
        "метке метода и дописывает найденное в очередь кандидатов, а решение "
        "по каждому принимает человек: правило, отличающее новую архитектуру "
        "от приложения существующей, ошибается, и цена ошибки — запись реестра "
        "о том, чего нет. Очередь показана на странице «Пробелы».",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="сверить и вернуть ошибку при расхождении")
    args = parser.parse_args()

    expected = render()
    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            sys.stderr.write(
                f"{OUT.relative_to(ROOT)} разошёлся с кодом сборщиков; "
                "выполните `python3 scripts/build_sources.py`\n"
            )
            return 1
        print("перечень ресурсов совпадает с кодом")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(expected, encoding="utf-8")
    print(f"перечень ресурсов записан: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
