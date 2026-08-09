"""Общие средства тестов: поддельный транспорт и записанные ответы источников."""

from tests.support.fake_transport import (
    FakeTransport,
    SourceBehaviour,
    load_fixture,
    standard_routes,
)

__all__ = [
    "FakeTransport",
    "SourceBehaviour",
    "load_fixture",
    "standard_routes",
]
