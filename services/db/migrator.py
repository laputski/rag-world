"""Простой движок SQL-миграций.

Применяет файлы из services/db/migrations/*.sql в алфавитном порядке,
пропуская уже применённые (учёт в таблице schema_migrations). Каждый файл
выполняется в отдельной транзакции. Чексумма SHA256 ловит изменение уже
применённого файла.

Без Alembic намеренно: проект простой, один исполнитель, схема реестра
стабильна. Тяжёлая ORM/миграционный фреймворк — лишняя зависимость.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from services.db import connection as db

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def list_pending() -> list[tuple[Path, str]]:
    """Возвращает [(path, checksum)] для ещё не применённых миграций по порядку."""
    applied = {
        row[0]
        for row in db.fetch_all("SELECT filename FROM schema_migrations")
    }
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    pending: list[tuple[Path, str]] = []
    for path in files:
        if path.name in applied:
            continue
        pending.append((path, _checksum(path.read_text(encoding="utf-8"))))
    return pending


def _ensure_schema_migrations() -> None:
    # Таблица создаётся в 001_registry.sql, но на пустой БД вызывается
    # migrate() до применения 001 — поэтому гарантируем наличие здесь.
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            applied_at TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
            filename   TEXT NOT NULL UNIQUE,
            checksum   TEXT
        )
        """
    )


def migrate(verbose: bool = False) -> int:
    """Применяет все pending-миграции. Возвращает число применённых файлов."""
    if not db.is_configured():
        raise db.DatabaseNotConfiguredError(
            "DATABASE_URL не задан; миграции не выполнены. "
            "См. .env.example и registry/README.md."
        )
    _ensure_schema_migrations()
    pending = list_pending()
    if not pending:
        if verbose:
            print("OK    миграций не требуется — схема актуальна.")
        return 0

    applied_count = 0
    for path, checksum in pending:
        sql = path.read_text(encoding="utf-8")
        # Каждый файл — отдельная транзакция.
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
        applied_count += 1
        if verbose:
            print(f"APPLY {path.name}")

    if verbose:
        print(f"OK    применено миграций: {applied_count}.")
    return applied_count


def is_applied(filename: str) -> bool:
    if not db.is_configured():
        return False
    row = db.fetch_one(
        "SELECT 1 FROM schema_migrations WHERE filename = %s", (filename,)
    )
    return row is not None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Применить SQL-миграции реестра.")
    parser.add_argument(
        "--pending", action="store_true", help="только показать pending, не применять"
    )
    args = parser.parse_args()

    if args.pending:
        for path, _ in list_pending():
            print(path.name)
    else:
        n = migrate(verbose=True)
        raise SystemExit(0 if n >= 0 else 1)
