from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ... import campaigns as fgcampaigns
from ...summary import campaign_markdown
from ..deps import Conn, Sim

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

LIST_COLS = """
    c.id, c.name, c.baseline, c.candidate, c.families, c.scenario_count, c.status, c.progress, c.error,
    c.created_at, c.started_at, c.finished_at, c.drives_per_second, c.tags,
    c.verdict->>'status' AS verdict, c.verdict->'flagged' AS flagged, (c.verdict->>'failures')::int AS failures
"""


class CampaignCreate(BaseModel):
    baseline: str
    candidate: str
    scenario_count: int = Field(700, ge=1, le=200_000)
    families: list[str] | None = None
    seed_start: int = Field(0, ge=0)
    name: str | None = None


def get_or_404(conn: psycopg.Connection, campaign_id: int) -> dict[str, Any]:
    c = fgcampaigns.get(conn, campaign_id)
    if c is None:
        raise HTTPException(404, f"no campaign {campaign_id}")
    return c


@router.post("", status_code=201)
def create(body: CampaignCreate, conn: Conn, sim: Sim) -> dict:
    """Queue a campaign. A worker picks it up; poll GET /api/campaigns/{id} for status and verdict."""
    if body.families:
        unknown = sorted(set(body.families) - set(sim.families()))
        if unknown:
            raise HTTPException(422, f"unknown scenario families: {', '.join(unknown)}")
    try:
        cid = fgcampaigns.create(conn, baseline=body.baseline, candidate=body.candidate,
                                 scenario_count=body.scenario_count, families=body.families,
                                 seed_start=body.seed_start, name=body.name)
    except fgcampaigns.CampaignError as exc:
        raise HTTPException(422, str(exc)) from exc
    return fgcampaigns.get(conn, cid)


@router.get("")
def list_campaigns(conn: Conn, status: str | None = None, include_benchmark: bool = False,
                   limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.execute(
        f"""
        SELECT {LIST_COLS} FROM campaigns c
         WHERE (%(status)s::text IS NULL OR c.status = %(status)s)
           AND (%(bench)s OR NOT (c.tags ? 'benchmark'))
         ORDER BY c.id DESC LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"status": status, "bench": include_benchmark, "limit": min(limit, 500), "offset": offset},
    ).fetchall()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, conn: Conn) -> dict:
    return get_or_404(conn, campaign_id)


@router.get("/{campaign_id}/metrics")
def metrics(campaign_id: int, conn: Conn) -> dict:
    get_or_404(conn, campaign_id)
    roles = conn.execute("SELECT * FROM campaign_role_metrics WHERE campaign_id = %s ORDER BY role",
                         (campaign_id,)).fetchall()
    families = conn.execute("SELECT * FROM campaign_family_metrics WHERE campaign_id = %s ORDER BY family, role",
                            (campaign_id,)).fetchall()
    return {"roles": roles, "families": families}


@router.get("/{campaign_id}/summary.md", response_class=PlainTextResponse)
def summary(campaign_id: int, conn: Conn, ui: str | None = None) -> str:
    """Verdict, KPIs and top clusters as markdown (for a PR comment or a CI job summary)."""
    get_or_404(conn, campaign_id)
    return campaign_markdown(conn, campaign_id, ui_base=ui)
