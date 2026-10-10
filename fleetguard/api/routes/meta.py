from __future__ import annotations

from fastapi import APIRouter

from ... import __version__
from ..deps import Conn, Sim

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health(conn: Conn, sim: Sim) -> dict:
    conn.execute("SELECT 1")
    return {"status": "ok", "version": __version__, "fgsim": sim.version()}


@router.get("/families")
def families(sim: Sim) -> list[str]:
    return sim.families()
