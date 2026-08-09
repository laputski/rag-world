"""Поддельный транспорт: прогон цепочки без сети.

Всё покрытие еженедельного прогона держится на этом. Пока цепочка ходит в сеть,
проверять нечего: результат зависит от того, что сегодня отдаёт архив
препринтов, а нездоровые случаи — отказ, ограничение частоты, испорченный
ответ — воспроизвести нельзя вовсе.

Транспорт отдаёт записанные ответы по подстроке адреса и умеет вести себя
плохо: отвечать отказом, молчать, возвращать мусор. Он считает обращения,
поэтому можно проверить и то, что источник опрошен, и то, что лишних запросов
нет.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sources"


def load_fixture(name: str) -> bytes:
    """Записанный ответ источника."""
    return (FIXTURES / name).read_bytes()


@dataclass
class SourceBehaviour:
    """Как источник отвечает: тело, код и число повторов отказа.

    `fail_times` позволяет описать источник, который сперва отвечает отказом по
    частоте обращений, а затем отдаёт данные, — иначе повтор с паузой проверить
    нечем.
    """

    body: bytes = b""
    status: int = 200
    fail_times: int = 0
    fail_status: int = 429


@dataclass
class FakeTransport:
    """Отдаёт заранее заданные ответы по подстроке адреса.

    Адрес, не совпавший ни с одним правилом, получает код 404: молчание об
    источнике, которого не ждали, лучше выдуманного ответа.
    """

    routes: dict[str, SourceBehaviour] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    _failures: dict[str, int] = field(default_factory=dict)

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        self.calls.append(url)
        for marker, behaviour in self.routes.items():
            if marker in url:
                seen = self._failures.get(marker, 0)
                if seen < behaviour.fail_times:
                    self._failures[marker] = seen + 1
                    return (behaviour.fail_status, b"")
                return (behaviour.status, behaviour.body)
        return (404, b"{}")

    def calls_matching(self, marker: str) -> list[str]:
        return [c for c in self.calls if marker in c]


def standard_routes() -> dict[str, SourceBehaviour]:
    """Здоровые ответы всех источников: основа, от которой отклоняются тесты."""
    return {
        "export.arxiv.org": SourceBehaviour(load_fixture("arxiv_entry.xml")),
        "api.openalex.org/works/doi": SourceBehaviour(
            load_fixture("openalex_preprint.json")
        ),
        "api.openalex.org/works?filter=title.search": SourceBehaviour(
            load_fixture("openalex_search.json")
        ),
        "api.github.com/repos/demo/demo/releases": SourceBehaviour(b"[]"),
        "api.github.com/repos/demo/demo": SourceBehaviour(
            load_fixture("github_repo.json")
        ),
        # Оглавления каталогов интеграций фреймворков.
        "contents": SourceBehaviour(load_fixture("github_contents.json")),
        "pypi.org/pypi": SourceBehaviour(load_fixture("pypi_meta.json")),
        "pypistats.org": SourceBehaviour(load_fixture("pypistats.json")),
    }


def route_without(routes: dict[str, SourceBehaviour], marker: str) -> dict:
    """Те же правила, но без одного источника: он ответит отказом."""
    return {k: v for k, v in routes.items() if k != marker}


def json_body(payload: object) -> bytes:
    return json.dumps(payload).encode()
