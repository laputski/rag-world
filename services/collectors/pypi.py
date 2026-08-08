"""Сборщик сведений о пакете: существование и число загрузок.

Загрузки пакета — второе достаточное условие уровня L4: они означают, что
технологией пользуются за пределами исходной работы. Вместе с присутствием во
фреймворках это единственные два машиночитаемых пути к L4, поэтому без обоих
сборщиков потолок собранных данных остаётся на L3.

Имя пакета берётся из поля записи и **не выводится из имени технологии**.
Догадка здесь недопустима: в индексе пакетов полно имён, похожих на названия
архитектур, и ошибка дала бы уровень, подтверждённый чужими загрузками. Запись
без имени пакета пропускается молча — это не ошибка, а отсутствие сведения.

Индекс пакетов не публикует число загрузок; его отдаёт отдельная служба
статистики. Если существование пакета подтвердилось, а статистика недоступна,
свидетельство о загрузках не создаётся: тип свидетельства называется
«загрузки», и подменять его фактом существования нельзя.
"""

from __future__ import annotations

import json
from datetime import date

from services.collectors.base import (
    CollectResult,
    HttpGetter,
    RawEvidence,
    is_allowed_host,
)

PYPI_API = "https://pypi.org/pypi"
STATS_API = "https://pypistats.org/api/packages"

#: Ниже этого порога загрузки за месяц не считаются свидетельством
#: распространённости: столько даёт непрерывная интеграция самих авторов.
MIN_MONTHLY_DOWNLOADS = 1000


def _get_json(http: HttpGetter, url: str) -> tuple[dict | None, str | None]:
    if not is_allowed_host(url):
        return None, f"домен вне allowlist: {url}"
    status, body = http.get(url, headers={"User-Agent": "rag-world/0.2"}, timeout=20)
    if status == 404:
        return None, None  # пакета нет — это ответ, а не сбой
    if status != 200:
        return None, f"код {status} от {url}"
    try:
        return json.loads(body), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"некорректный ответ от {url}"


def collect_pypi(
    technology_id: str,
    package: str,
    *,
    http: HttpGetter,
    today: date | None = None,
) -> CollectResult:
    """Проверить пакет и собрать число загрузок за последний месяц."""
    today = today or date.today()
    result = CollectResult(source_name="pypi", technology_id=technology_id)

    meta, error = _get_json(http, f"{PYPI_API}/{package}/json")
    if error:
        result.errors.append(f"{technology_id}: {error}")
        return result
    if meta is None:
        result.errors.append(f"{technology_id}: пакет {package!r} не найден")
        return result

    # Служба статистики принимает нормализованное имя: «FlagEmbedding» она не
    # знает, а «flagembedding» знает.
    stats, error = _get_json(http, f"{STATS_API}/{package.lower()}/recent")
    if error or stats is None:
        # Пакет есть, статистики нет. Свидетельство о загрузках не создаётся:
        # существование пакета — другое утверждение.
        result.errors.append(
            f"{technology_id}: статистика загрузок {package!r} недоступна"
        )
        return result

    monthly = int((stats.get("data") or {}).get("last_month") or 0)
    if monthly < MIN_MONTHLY_DOWNLOADS:
        result.skipped.append(
            f"{technology_id}: загрузок за месяц {monthly}, ниже порога"
        )
        return result

    version = (meta.get("info") or {}).get("version", "")
    result.evidence.append(RawEvidence(
        technology_id=technology_id,
        type="package_downloads",
        value=f"package={package}; version={version}; downloads_last_month={monthly}",
        source=f"https://pypi.org/project/{package}/",
        fetched_at=today,
        obtained_by="auto",
        verified=False,
    ))
    return result
