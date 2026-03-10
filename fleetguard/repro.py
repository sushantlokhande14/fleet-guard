"""Reproduce a stored failure from scratch and check it matches.

Every failure carries enough to replay it: scenario family + seed and the two
builds' overrides. verify() re-runs `fgsim compare` and checks that both drives
come out the same as what was ingested: outcome, summary metrics, and the event
timeline. Postgres stores metrics as float4, so numbers are compared with a
small relative tolerance.
"""

from __future__ import annotations

import json
import math
import shlex
from datetime import UTC, datetime
from typing import Any

import psycopg

from .ingest import DRIVE_COLS
from .sim import Fgsim

REL_TOL = 1e-4
ABS_TOL = 1e-3


def _close(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return math.isclose(float(a), float(b), rel_tol=REL_TOL, abs_tol=ABS_TOL)


def load_case(conn: psycopg.Connection, failure_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT f.id, f.campaign_id, f.scenario_id, f.category, s.family, s.seed,
               c.baseline, c.candidate,
               bb.overrides AS baseline_overrides, cb.overrides AS candidate_overrides,
               p.baseline_drive, p.candidate_drive
          FROM failures f
          JOIN campaigns c ON c.id = f.campaign_id
          JOIN scenarios s ON s.id = f.scenario_id
          JOIN builds bb ON bb.name = c.baseline
          JOIN builds cb ON cb.name = c.candidate
          JOIN pairs p ON p.campaign_id = f.campaign_id AND p.scenario_id = f.scenario_id
         WHERE f.id = %s
        """,
        (failure_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"no failure {failure_id}")
    return row


def command(case: dict[str, Any]) -> str:
    """Shell command an engineer can paste to replay the pair."""
    b = shlex.quote(json.dumps(case["baseline_overrides"], separators=(",", ":")))
    c = shlex.quote(json.dumps(case["candidate_overrides"], separators=(",", ":")))
    return (f"echo {b} > baseline.json && echo {c} > candidate.json && "
            f"fgsim compare --family {case['family']} --seed {case['seed']} "
            f"--baseline baseline.json --candidate candidate.json --frames-prefix {case['scenario_id']}")


def _diff_drive(conn: psycopg.Connection, drive_id: int, fresh: dict[str, Any], role: str) -> list[str]:
    stored = conn.execute("SELECT * FROM drives WHERE id = %s", (drive_id,)).fetchone()
    out = []
    for col in DRIVE_COLS:
        if not _close(stored[col], fresh[col]):
            out.append(f"{role}.{col}: stored {stored[col]!r} vs replay {fresh[col]!r}")
    events = conn.execute(
        "SELECT t, kind, detail FROM drive_events WHERE drive_id = %s ORDER BY t, id", (drive_id,)
    ).fetchall()
    stored_ev = sorted((round(e["t"], 2), e["kind"], e["detail"]) for e in events)
    fresh_ev = sorted((round(e["t"], 2), e["kind"], e["detail"]) for e in fresh["events"])
    if stored_ev != fresh_ev:
        out.append(f"{role}.events: stored {len(stored_ev)} vs replay {len(fresh_ev)}"
                   " (or their times/kinds differ)")
    return out


def verify(conn: psycopg.Connection, failure_id: int, sim: Fgsim | None = None) -> dict[str, Any]:
    sim = sim or Fgsim()
    case = load_case(conn, failure_id)
    replay = sim.compare(case["family"], int(case["seed"]),
                         case["baseline_overrides"], case["candidate_overrides"])
    mismatches = (_diff_drive(conn, case["baseline_drive"], replay["baseline"], "baseline")
                  + _diff_drive(conn, case["candidate_drive"], replay["candidate"], "candidate"))
    ok = not mismatches
    conn.execute("UPDATE failures SET repro_verified = %s, repro_checked_at = %s WHERE id = %s",
                 (ok, datetime.now(UTC), failure_id))
    return {"failure_id": failure_id, "reproduced": ok, "mismatches": mismatches, "command": command(case),
            "replay": replay}
