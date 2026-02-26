"""Postgres access: connections and schema migrations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import get_settings


def connect(url: str | None = None, **kwargs) -> psycopg.Connection:
    return psycopg.connect(url or get_settings().database_url, row_factory=dict_row, **kwargs)


@contextmanager
def session(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Connection that commits on success and rolls back on error."""
    conn = connect(url)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def migrations(directory: Path | None = None) -> list[Path]:
    d = Path(directory or get_settings().migrations_dir)
    return sorted(d.glob("[0-9][0-9][0-9]_*.sql"))


def migrate(conn: psycopg.Connection, directory: Path | None = None) -> list[str]:
    """Apply pending migrations in order, each in its own transaction. Returns what ran."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    # one migrator at a time (api and worker both migrate on start)
    conn.execute("SELECT pg_advisory_lock(727274)")
    try:
        applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        ran = []
        for path in migrations(directory):
            version = path.stem
            if version in applied:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            ran.append(version)
        return ran
    finally:
        conn.execute("SELECT pg_advisory_unlock(727274)")
        conn.commit()


def reset(conn: psycopg.Connection) -> None:
    """Drop everything. Tests only."""
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.commit()
