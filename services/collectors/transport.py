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
    # Пять обращений в секунду индекс не выдерживает и отвечает отказом по
    # частоте даже с повторами. Секунда — то, что проходит и в общем потоке;
    # с назначенной почтой можно было бы чаще, но настройка необязательна, и
    # прогон должен работать и без неё.
    "api.openalex.org": 1.0,
    "api.github.com": 1.0,
    "pypi.org": 0.2,
}
DEFAULT_DELAY = 0.5

#: Сколько раз повторить запрос при отказе из-за частоты обращений.
RETRIES_ON_RATE_LIMIT = 3

#: Как обращение представляется площадке.
#:
#: Обращение без представления многие площадки отклоняют как роботское, и отказ
#: этот неотличим от «страница закрыта». Один такой случай уже был: статья
#: справочника отвечала отказом, и лишь с представлением стало видно, что её не
#: существует вовсе. Молчание о себе не делает обращение вежливее — оно делает
#: ответ менее правдивым.
DEFAULT_USER_AGENT = "rag-world/0.2 (registry; +https://rag-world.onrender.com)"


class RequestsTransport:
    """HTTP-транспорт поверх requests с соблюдением вежливой частоты.

    `allow_any_host` снимает перечень доменов и предназначен ровно для одной
    задачи — проверки разрешимости ссылок самого реестра. Перечень существует,
    чтобы сбор свидетельств не уходил по адресам, встреченным в содержимом
    источника; ссылки реестра, наоборот, вписаны нами, и половина из них ведёт
    на площадки, которых в перечне нет и быть не должно.
    """

    def __init__(self, allow_any_host: bool = False) -> None:
        self._last_call: dict[str, float] = {}
        self._allow_any_host = allow_any_host

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
        if not self._allow_any_host and not is_allowed_host(url):
            return (403, b"host not in allowlist")

        host = (urlparse(url).hostname or "").lower()
        for attempt in range(RETRIES_ON_RATE_LIMIT + 1):
            self._wait(host)
            try:
                # Представление подставляется, если вызывающий его не задал:
                # одно место вместо повторения в каждом сборщике.
                sent = {"User-Agent": DEFAULT_USER_AGENT, **(headers or {})}
                resp = requests.get(url, headers=sent, timeout=timeout)
            except requests.RequestException as exc:
                return (0, str(exc).encode())
            if resp.status_code != 429 or attempt == RETRIES_ON_RATE_LIMIT:
                return (resp.status_code, resp.content)
            # Отказ по частоте: ждём дольше обычного и пробуем ещё раз.
            time.sleep(HOST_DELAYS.get(host, DEFAULT_DELAY) * (attempt + 2))
        return (429, b"rate limited")
