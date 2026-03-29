"""Telemetry for the replay view.

Telemetry is only stored for flagged pairs (and only up to a cap per campaign).
Every drive is deterministic, so when nothing was stored the frames are simply
regenerated with fgsim compare: same seed, same builds, same result.
"""

from __future__ import annotations

import csv
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg
from fastapi import APIRouter

from ... import repro
from ...ingest import FRAME_COLS
from ...sim import Fgsim
from ..deps import Conn, Sim
from .failures import load_failure

router = APIRouter(prefix="/api/failures", tags=["replay"])

INT_COLS = {"lead_id", "deadline_miss", "n_tracks", "n_relevant", "n_missed", "n_phantom", "engaged"}


def _columnar(rows: list[dict[str, Any]]) -> dict[str, list]:
    return {c: [r[c] for r in rows] for c in FRAME_COLS}


def _stored(conn: psycopg.Connection, drive_id: int) -> dict[str, list] | None:
    rows = conn.execute(f"SELECT {', '.join(FRAME_COLS)} FROM telemetry_frames WHERE drive_id = %s ORDER BY t",
                        (drive_id,)).fetchall()
    return _columnar(rows) if rows else None


def _parse_csv(path: Path) -> dict[str, list]:
    def cell(col: str, v: str):
        if v == "":
            return None
        return int(v) if col in INT_COLS else float(v)

    with open(path, newline="") as f:
        rows = [{c: cell(c, r[c]) for c in FRAME_COLS} for r in csv.DictReader(f)]
    return _columnar(rows)


def _regenerate(sim: Fgsim, case: dict[str, Any]) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        prefix = str(Path(tmp) / "pair")
        sim.compare(case["family"], int(case["seed"]), case["baseline_overrides"], case["candidate_overrides"],
                    frames_prefix=prefix)
        return _parse_csv(Path(prefix + ".baseline.csv")), _parse_csv(Path(prefix + ".candidate.csv"))


@router.get("/{failure_id}/telemetry")
def telemetry(failure_id: int, conn: Conn, sim: Sim) -> dict:
    load_failure(conn, failure_id)
    case = repro.load_case(conn, failure_id)
    base = _stored(conn, case["baseline_drive"])
    cand = _stored(conn, case["candidate_drive"])
    source = "stored"
    if base is None or cand is None:
        base, cand = _regenerate(sim, case)
        source = "replayed"
    return {"source": source, "columns": FRAME_COLS, "baseline": base, "candidate": cand}


@lru_cache(maxsize=256)
def _geometry(sim_path: str, family: str, seed: int) -> dict:
    return Fgsim(sim_path).scenario(family, seed, geometry=True)


@router.get("/{failure_id}/scenario")
def scenario(failure_id: int, conn: Conn, sim: Sim) -> dict:
    case = repro.load_case(conn, load_failure(conn, failure_id)["id"])
    return _geometry(sim.path, case["family"], int(case["seed"]))


@router.post("/{failure_id}/repro")
def verify(failure_id: int, conn: Conn, sim: Sim) -> dict:
    """Re-run the pair from its seed and build definitions and compare with what was stored."""
    load_failure(conn, failure_id)
    r = repro.verify(conn, failure_id, sim)
    return {k: r[k] for k in ("failure_id", "reproduced", "mismatches", "command")}
