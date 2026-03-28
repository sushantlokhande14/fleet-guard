from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException

from ... import builds as fgbuilds
from ... import repro
from ..deps import Conn
from .campaigns import get_or_404

router = APIRouter(prefix="/api", tags=["failures"])


@router.get("/campaigns/{campaign_id}/failures")
def list_failures(campaign_id: int, conn: Conn, category: str | None = None, family: str | None = None,
                  signature: str | None = None, min_severity: int = 1, limit: int = 100,
                  offset: int = 0) -> dict:
    get_or_404(conn, campaign_id)
    params = {"c": campaign_id, "cat": category, "fam": family, "sig": signature, "sev": min_severity,
              "limit": min(limit, 500), "offset": offset}
    where = """
        f.campaign_id = %(c)s
        AND (%(cat)s::text IS NULL OR f.category = %(cat)s)
        AND (%(fam)s::text IS NULL OR s.family = %(fam)s)
        AND (%(sig)s::text IS NULL OR f.signature = %(sig)s)
        AND f.severity >= %(sev)s
    """
    total = conn.execute(
        f"SELECT count(*) AS n FROM failures f JOIN scenarios s ON s.id = f.scenario_id WHERE {where}", params
    ).fetchone()["n"]
    items = conn.execute(
        f"""
        SELECT f.id, f.scenario_id, s.family, s.weather, f.category, f.secondary, f.severity, f.score,
               f.first_t, f.signature, f.repro_verified
          FROM failures f JOIN scenarios s ON s.id = f.scenario_id
         WHERE {where}
         ORDER BY f.severity DESC, f.score DESC, f.id
         LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    ).fetchall()
    return {"total": total, "items": items}


@router.get("/campaigns/{campaign_id}/clusters")
def clusters(campaign_id: int, conn: Conn) -> list[dict]:
    """Failures grouped by signature: one row per probable bug, biggest first."""
    get_or_404(conn, campaign_id)
    return conn.execute(
        """
        SELECT f.signature, f.category, min(s.family) AS family, count(*) AS failures,
               max(f.severity) AS severity, round(avg(f.score)::numeric, 3)::float AS mean_score,
               (array_agg(f.id ORDER BY f.score DESC))[1] AS example_id
          FROM failures f JOIN scenarios s ON s.id = f.scenario_id
         WHERE f.campaign_id = %s
         GROUP BY f.signature, f.category
         ORDER BY failures DESC, f.signature
        """,
        (campaign_id,),
    ).fetchall()


def _drive(conn: psycopg.Connection, drive_id: int) -> dict[str, Any]:
    d = conn.execute("SELECT * FROM drives WHERE id = %s", (drive_id,)).fetchone()
    d["events"] = conn.execute(
        "SELECT t, kind, severity, value, duration, detail FROM drive_events WHERE drive_id = %s ORDER BY t, id",
        (drive_id,),
    ).fetchall()
    d["has_telemetry"] = conn.execute("SELECT EXISTS (SELECT 1 FROM telemetry_frames WHERE drive_id = %s) AS e",
                                      (drive_id,)).fetchone()["e"]
    return d


def load_failure(conn: psycopg.Connection, failure_id: int) -> dict[str, Any]:
    f = conn.execute("SELECT * FROM failures WHERE id = %s", (failure_id,)).fetchone()
    if f is None:
        raise HTTPException(404, f"no failure {failure_id}")
    return f


@router.get("/failures/{failure_id}")
def failure_detail(failure_id: int, conn: Conn) -> dict:
    f = load_failure(conn, failure_id)
    c = conn.execute("SELECT id, name, baseline, candidate, status FROM campaigns WHERE id = %s",
                     (f["campaign_id"],)).fetchone()
    s = conn.execute("SELECT * FROM scenarios WHERE id = %s", (f["scenario_id"],)).fetchone()
    p = conn.execute("SELECT * FROM pairs WHERE campaign_id = %s AND scenario_id = %s",
                     (f["campaign_id"], f["scenario_id"])).fetchone()
    params = {r["name"]: r["params"] for r in conn.execute(
        "SELECT name, params FROM builds WHERE name = ANY(%s)", ([c["baseline"], c["candidate"]],))}
    case = repro.load_case(conn, failure_id)
    return {
        "failure": f,
        "campaign": c,
        "scenario": s,
        "pair": p,
        "baseline": _drive(conn, p["baseline_drive"]),
        "candidate": _drive(conn, p["candidate_drive"]),
        "build_diff": [ch.as_dict() for ch in fgbuilds.diff(params[c["baseline"]], params[c["candidate"]])],
        "repro_command": repro.command(case),
    }
