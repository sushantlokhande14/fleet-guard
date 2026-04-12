from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...diagnostics import report as fgreport
from ..deps import Conn
from .failures import load_failure

router = APIRouter(prefix="/api/failures", tags=["reports"])


@router.post("/{failure_id}/report", status_code=201)
def create_report(failure_id: int, request: Request, conn: Conn, llm: bool = True) -> dict:
    """Generate a diagnostic report. With llm=true the narrative comes from the configured model (local
    Ollama by default) when it passes the guard; otherwise the deterministic template is used."""
    load_failure(conn, failure_id)
    client = request.app.state.llm_factory() if llm else None
    try:
        return fgreport.generate(conn, failure_id, llm=client)
    finally:
        if client is not None:
            client.close()


@router.get("/{failure_id}/report")
def latest_report(failure_id: int, conn: Conn) -> dict:
    load_failure(conn, failure_id)
    r = fgreport.latest(conn, failure_id)
    if r is None:
        raise HTTPException(404, "no report yet; POST to generate one")
    return r


@router.get("/{failure_id}/reports")
def report_history(failure_id: int, conn: Conn) -> list[dict]:
    load_failure(conn, failure_id)
    return conn.execute(
        "SELECT id, generator, model, meta, created_at FROM reports WHERE failure_id = %s ORDER BY created_at DESC",
        (failure_id,),
    ).fetchall()
