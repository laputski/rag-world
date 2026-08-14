"""Настоящие данные реестра проходят собственную проверку.

Проверка данных существовала и раньше, но запускалась только целью `make
validate` и отдельным шагом непрерывной интеграции. Все тесты, касавшиеся её,
подменяли каталог данных временным: они проверяли **правило**, а не то, чему
правило применяется.

Отсюда разрыв, который однажды и сработал. Правка записи реестра проходила
`make test` целиком зелёной, потому что настоящих данных ни один тест не читал,
и нарушение обнаруживалось после отправки, на чужой машине, в задании
непрерывной интеграции. Разработчик при этом видел зелёный прогон и был вправе
считать работу законченной.

Проверка сети не требует: сюда входят схема, ссылочная целостность,
происхождение чисел и согласованность отметок об осмотре. Разрешимость адресов
проверяется отдельно, по расписанию, потому что она зависит от чужих служб.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data  # noqa: E402


def test_registry_passes_its_own_validation():
    problems = validate_data.check_registry()
    assert not problems, (
        "данные реестра не проходят собственную проверку:\n  "
        + "\n  ".join(problems)
    )


def test_every_file_is_named_after_the_record_inside():
    """Отдельно, потому что расхождение здесь удваивает запись при сохранении."""
    assert validate_data.check_filenames() == []


def test_validation_needs_no_network():
    """Проверка обязана работать офлайн, иначе прогон зависит от чужих служб.

    Разрешимость адресов вынесена в отдельный ключ и в отдельное расписание:
    отказ издательства не должен красить прогон в красный.
    """
    import services.collectors.transport as transport

    def refuse(*args, **kwargs):  # pragma: no cover — вызов означал бы отказ
        raise AssertionError("проверка данных обратилась в сеть")

    original = transport.RequestsTransport.get
    transport.RequestsTransport.get = refuse
    try:
        validate_data.check_registry()
    finally:
        transport.RequestsTransport.get = original
