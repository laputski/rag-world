"""HTTP-транспорт сборщиков.

Обёртка над requests, реализующая интерфейс, который сборщики ожидают. В тестах
подменяется заглушкой, поэтому сеть в них не нужна.

Транспорт соблюдает два правила, без которых автономный сбор быстро упрётся в
запреты источников:

* **перечень разрешённых доменов** — обращение к постороннему адресу не
  выполняется вовсе, даже если сборщик ошибся;
* **вежливая частота** — между обращениями к одному хосту выдерживается пауза.
  Архив препринтов просит не чаще одного запроса в три секунды и отвечает
  отказом при нарушении; открытые индексы терпимее, но и им не следует слать
  запросы без пауз.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

from services.collectors.base import is_allowed_host

#: Минимальная пауза между обращениями к одному хосту, в секундах.
HOST_DELAYS: dict[str, float] = {
    "export.arxiv.org": 4.0,
    "arxiv.org": 4.0,
    "api.openalex.org": 0.2,
    "api.github.com": 1.0,
    "pypi.org": 0.2,
}
DEFAULT_DELAY = 0.5

#: Сколько раз повторить запрос при отказе из-за частоты обращений.
RETRIES_ON_RATE_LIMIT = 3


class RequestsTransport:
    """HTTP-транспорт поверх requests с соблюдением вежливой частоты."""

    def __init__(self) -> None:
        self._last_call: dict[str, float] = {}

    def _wait(self, host: str) -> None:
        delay = HOST_DELAYS.get(host, DEFAULT_DELAY)
        previous = self._last_call.get(host)
        if previous is not None:
            elapsed = time.monotonic() - previous
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self._last_call[host] = time.monotonic()

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        # Двойная проверка перечня доменов: сборщики проверяют его сами, но
        # транспорт не должен обращаться к постороннему адресу и при их ошибке.
        if not is_allowed_host(url):
            return (403, b"host not in allowlist")

        host = (urlparse(url).hostname or "").lower()
        for attempt in range(RETRIES_ON_RATE_LIMIT + 1):
            self._wait(host)
            try:
                resp = requests.get(url, headers=headers or {}, timeout=timeout)
            except requests.RequestException as exc:
                return (0, str(exc).encode())
            if resp.status_code != 429 or attempt == RETRIES_ON_RATE_LIMIT:
                return (resp.status_code, resp.content)
            # Отказ по частоте: ждём дольше обычного и пробуем ещё раз.
            time.sleep(HOST_DELAYS.get(host, DEFAULT_DELAY) * (attempt + 2))
        return (429, b"rate limited")
