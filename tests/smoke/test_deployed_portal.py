"""Дымовая проверка развёрнутого портала.

Отдельно от основного набора и в него не входит: она требует сети и проверяет
не код, а результат развёртывания. Смешивать их нельзя — тест, падающий из-за
чужой сети, перестают читать вместе со всеми остальными.

Запуск::

    pytest tests/smoke -m network
    make smoke

Проверяется то, что ломается именно при развёртывании и не ловится ничем
другим: правило переписывания адресов, наличие файлов данных, отсутствие
обращений к внешним источникам и совпадение опубликованного с репозиторием.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

requests = pytest.importorskip("requests")

pytestmark = pytest.mark.network

#: Адрес развёрнутого портала. Он же указан в render.yaml и в представлении
#: транспорта: обращаясь к чужим площадкам, портал называет себя этим адресом.
#: Собственное имя портала. Площадка отвечает и по своему адресу
#: (rag-world.onrender.com), но проверяется то, что видит читатель.
BASE_URL = "https://ragworld.org"

HEADERS = {"User-Agent": "rag-world/0.2 (smoke check)"}
TIMEOUT = 30


@pytest.fixture(scope="module")
def index_html() -> str:
    resp = requests.get(BASE_URL + "/", headers=HEADERS, timeout=TIMEOUT)
    assert resp.status_code == 200
    return resp.text


def get(path: str):
    return requests.get(BASE_URL + path, headers=HEADERS, timeout=TIMEOUT)


# ─── Доступность разделов ────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/", "/registry", "/changes", "/digest", "/article", "/about"])
def test_sections_answer(path):
    assert get(path).status_code == 200, path


def test_direct_link_to_a_card_opens(index_html):
    """Прямой адрес карточки — обязательное условие цитируемости.

    Без правила переписывания статический хостинг вернул бы «страницы нет», и
    ссылка на запись из чужой работы вела бы в пустоту.
    """
    resp = get("/tech/pathrag")
    assert resp.status_code == 200
    assert "<div id=\"root\">" in resp.text or "<title>" in resp.text


def test_unknown_address_gets_a_human_answer():
    """Правило переписывания отдаёт index.html на любой адрес.

    Значит опечатка доходит до приложения, и читатель обязан увидеть внятный
    ответ, а не отладочный экран маршрутизатора с обращением к разработчику.
    Проверяется по собранной странице: сам текст подставляется на клиенте,
    поэтому здесь достаточно, что адрес обслужен и отдана оболочка портала.
    """
    resp = get("/такого-адреса-нет")
    assert resp.status_code == 200
    assert "Unexpected Application Error" not in resp.text


# ─── Данные ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "registry.json", "map.json", "changes.json", "stats.json", "digest.json", "feed.xml",
])
def test_data_files_are_published(name):
    resp = get(f"/data/{name}")
    assert resp.status_code == 200, name
    assert resp.content, name


def test_published_data_matches_the_repository():
    """Развёрнуто то, что лежит в репозитории.

    Расхождение означает, что развёртывание отстало или не прошло, а портал
    при этом выглядит исправным: он показывает данные, просто вчерашние.
    """
    live = get("/data/registry.json").json()
    local = json.loads(
        (ROOT / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    assert live["count"] == local["count"], (
        f"на площадке {live['count']} записей, в репозитории {local['count']}"
    )
    assert live["built_at"] == local["built_at"], (
        f"на площадке собрано {live['built_at']}, в репозитории {local['built_at']}"
    )


def test_assets_are_served_not_rewritten(index_html):
    """Ресурсы обязаны отдаваться собой, а не оболочкой портала.

    Правило переписывания ловит любой неизвестный адрес, поэтому проверка по
    коду ответа бессмысленна: 200 вернётся и на несуществующий файл. Смотреть
    надо на тип содержимого.
    """
    assets = re.findall(r"/assets/[A-Za-z0-9._-]+\.(?:js|css)", index_html)
    assert assets, "в собранной странице нет ссылок на ресурсы"
    for path in assets[:2]:
        resp = get(path)
        assert resp.status_code == 200, path
        assert "text/html" not in resp.headers.get("Content-Type", ""), (
            f"{path} отдан оболочкой портала вместо файла"
        )


# ─── Самодостаточность ───────────────────────────────────────────────────────


def test_page_asks_no_external_host(index_html):
    """Портал не должен зависеть от чужих площадок при отрисовке.

    Шрифты и стили встроены в сборку намеренно: обращение к стороннему хосту
    делает портал заложником его доступности и сообщает читателя третьей
    стороне.
    """
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', index_html)
    allowed = (BASE_URL,)
    stray = [u for u in external if not u.startswith(allowed)]
    assert not stray, f"страница обращается наружу: {stray[:5]}"
