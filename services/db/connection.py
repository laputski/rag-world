"""Соединение с локальной базой реестра (PostgreSQL).

Реестр продакшена живёт в каталоге `data/` под управлением git. База остаётся
вспомогательным инструментом: она нужна для разовой миграции накопленных записей
в файлы и для локальных экспериментов. Конфигурация — переменная окружения
DATABASE_URL.

Слой доступа к данным живёт в services/db/repository.py, модели записей — в
services/db/models.py. Здесь только пул соединений и вспомогательная функция
выполнения запросов.

При отсутствии DATABASE_URL модуль не мешает работе остальных средств: вызывающий
код получает понятную ошибку вместо отказа на импорте.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    from psycopg import Connection, connect
    # psycopg_pool может быть установлен как отдельный пакет (psycopg_pool),
    # так и подключаться как psycopg.pool в некоторых сборках. Пробуем оба.
    try:
        from psycopg.pool import ConnectionPool  # type: ignore[attr-defined]
    except ImportError:
        from psycopg_pool import ConnectionPool  # type: ignore[no-redef]
except ImportError:  # pragma: no cover
    Connection = None  # type: ignore[assignment, misc]
    connect = None  # type: ignore[assignment]
    ConnectionPool = None  # type: ignore[assignment, misc]


_POOL: "ConnectionPool | None" = None


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL не задан — реестр технологий недоступен."""


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def is_configured() -> bool:
    return bool(database_url())


def _build_dsn(url: str) -> str:
    # render.com и большинство провайдеров отдают готовый postgresql:// DSN.
    # psycopg3 принимает его напрямую. Ничего перекраивать не нужно.
    return url


def get_pool() -> "ConnectionPool":
    """Лениво создаёт и возвращает процессный пул соединений.

    Повторные вызовы возвращают тот же пул. При отсутствии DATABASE_URL
    поднимает DatabaseNotConfiguredError — вызывающий код должен это обработать.
    """
    global _POOL
    if _POOL is not None:
        return _POOL
    # Сначала проверяем конфигурацию: отсутствие DATABASE_URL — ожидаемая
    # ситуация (локальный запуск без БД), это НЕ ошибка установки.
    url = database_url()
    if not url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL не задан; реестр технологий недоступен. "
            "См. .env.example и registry/README.md (STAGE-6 Ф1)."
        )
    # DATABASE_URL задан, но psycopg не установлен — это уже ошибка окружения.
    if ConnectionPool is None:  # pragma: no cover
        raise RuntimeError(
            "psycopg не установлен. Установите: pip install \"psycopg[binary]\""
        )
    # min_size=1, max_size=8 — разумные значения для одного инстанса API
    # на starter-плане render.com. При росте — вынести в конфигурацию.
    _POOL = ConnectionPool(
        conninfo=_build_dsn(url),
        min_size=1,
        max_size=8,
        open=True,
    )
    return _POOL


@contextmanager
def connection() -> Iterator["Connection"]:
    """Контекстный менеджер: берёт соединение из пула и возвращает его обратно.

    Использование::

        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM technologies")
                rows = cur.fetchall()
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def execute(sql: str, params: tuple[Any, ...] | None = None) -> None:
    """Выполнить запрос без возврата строк (DDL, INSERT, UPDATE)."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())


def fetch_all(
    sql: str, params: tuple[Any, ...] | None = None
) -> list[tuple[Any, ...]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def fetch_one(
    sql: str, params: tuple[Any, ...] | None = None
) -> tuple[Any, ...] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def close_pool() -> None:
    """Закрыть пул (для тестов и аккуратного завершения)."""
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None


def check_connection() -> bool:
    """Пинг БД. True — соединение есть, False — БД не сконфигурирована/недоступна."""
    if not is_configured():
        return False
    try:
        fetch_one("SELECT 1")
        return True
    except Exception:
        return False
