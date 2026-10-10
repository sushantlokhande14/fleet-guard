"""Data access for builds and campaigns."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .builds import Registry


def sync_builds(conn: psycopg.Connection, registry: Registry) -> int:
    """Upsert every registry build (overrides and effective params) into the builds table."""
    n = 0
    for name in registry.names():
        b = registry.get(name)
        conn.execute(
            """
            INSERT INTO builds (name, parent, description, overrides, params)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
               SET parent = EXCLUDED.parent, description = EXCLUDED.description,
                   overrides = EXCLUDED.overrides, params = EXCLUDED.params
            """,
            (name, b.parent, b.description, Jsonb(registry.overrides(name)), Jsonb(registry.effective(name))),
        )
        n += 1
    return n


def upsert_build(conn: psycopg.Connection, name: str, overrides: dict, params: dict,
                 description: str = "", parent: str | None = None) -> None:
    """Register an ad-hoc build (seeded regressions are created this way)."""
    conn.execute(
        """
        INSERT INTO builds (name, parent, description, overrides, params)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE
           SET overrides = EXCLUDED.overrides, params = EXCLUDED.params, description = EXCLUDED.description
        """,
        (name, parent, description, Jsonb(overrides), Jsonb(params)),
    )


def get_build(conn: psycopg.Connection, name: str) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM builds WHERE name = %s", (name,)).fetchone()


def list_builds(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(
        "SELECT name, parent, description, created_at FROM builds ORDER BY created_at, name"
    ).fetchall()
