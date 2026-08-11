"""Перечень ресурсов не должен расходиться с кодом сборщиков.

Перечень порождается из констант самих сборщиков, поэтому написать в нём
неправду нельзя. Но можно забыть пересборку после переезда чужого каталога, и
тогда документ будет спокойно утверждать вчерашнее. Переезд уже случался:
интеграции LangChain ушли из `libs/community` в `libs/langchain/langchain_classic`.

Тот же приём, что со схемой измерений для интерфейса: сгенерированный файл
сверяется с генератором, а не проверяется на правдоподобие.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_sources  # noqa: E402


def test_sources_file_exists():
    assert build_sources.OUT.exists(), (
        "перечень ресурсов отсутствует; выполните "
        "`python3 scripts/build_sources.py`"
    )


def test_sources_file_matches_the_collectors():
    actual = build_sources.OUT.read_text(encoding="utf-8")
    assert actual == build_sources.render(), (
        "перечень ресурсов разошёлся с кодом сборщиков; выполните "
        "`python3 scripts/build_sources.py` и не правьте файл вручную"
    )


def test_every_polled_address_is_listed():
    """Адрес, опрашиваемый кодом, обязан быть в перечне.

    Новый сборщик легко завести и легко забыть описать. Тогда портал ходит
    туда, куда по документам не ходит, и узнать об этом можно только чтением
    кода — ровно то состояние, ради выхода из которого перечень заведён.
    """
    listed = build_sources.render()
    missing = [url for url in build_sources.PURPOSE if url not in listed]
    assert not missing, f"адреса нет в перечне: {missing}"

    # Обратная сторона: перечень описывает только то, что существует в коде.
    import re

    declared = set()
    for module in ("arxiv", "openalex", "github", "pypi", "frameworks"):
        text = (ROOT / "services" / "collectors" / f"{module}.py").read_text(
            encoding="utf-8"
        )
        declared |= set(re.findall(r'^[A-Z_]+ *= *"(https?://[^"]+)"', text, re.M))

    undocumented = sorted(
        url for url in declared
        if url not in build_sources.PURPOSE and url not in listed
    )
    assert not undocumented, (
        f"сборщики ходят по адресам, которых нет в перечне: {undocumented}. "
        "Добавьте назначение в PURPOSE и пересоберите перечень."
    )
