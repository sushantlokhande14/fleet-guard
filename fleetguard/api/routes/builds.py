from __future__ import annotations

import psycopg
from fastapi import APIRouter, HTTPException

from ... import builds as fgbuilds
from ..deps import Conn

router = APIRouter(prefix="/api/builds", tags=["builds"])


@router.get("")
def list_builds(conn: Conn, include_seeded: bool = False) -> list[dict]:
    return conn.execute(
        "SELECT name, parent, description, overrides, created_at FROM builds"
        " WHERE %s OR name NOT LIKE 'seeded/%%' ORDER BY created_at, name",
        (include_seeded,),
    ).fetchall()


def _get(conn: psycopg.Connection, name: str) -> dict:
    row = conn.execute("SELECT * FROM builds WHERE name = %s", (name,)).fetchone()
    if row is None:
        raise HTTPException(404, f"unknown build {name}")
    return row


@router.get("/{name:path}/diff/{other:path}")
def diff(name: str, other: str, conn: Conn) -> list[dict]:
    a, b = _get(conn, name), _get(conn, other)
    return [c.as_dict() for c in fgbuilds.diff(a["params"], b["params"])]


@router.get("/{name:path}")
def get_build(name: str, conn: Conn) -> dict:
    return _get(conn, name)
