"""Campaigns: one baseline build vs one candidate build over a scenario set."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import db as fgdb
from .config import get_settings
from .ingest import ingest_batch
from .sim import Fgsim

ALL_FAMILIES = [
    "construction_shift", "highway_follow", "intersection_turn", "ped_crossing",
    "s_curve", "stop_and_go", "urban_cut_in",
]


class CampaignError(RuntimeError):
    pass


def create(conn: psycopg.Connection, *, baseline: str, candidate: str, scenario_count: int,
           families: list[str] | None = None, seed_start: int = 0, name: str | None = None,
           tags: dict | None = None) -> int:
    for b in (baseline, candidate):
        if conn.execute("SELECT 1 FROM builds WHERE name = %s", (b,)).fetchone() is None:
            raise CampaignError(f"unknown build {b}")
    fams = families or ALL_FAMILIES
    row = conn.execute(
        """
        INSERT INTO campaigns (name, baseline, candidate, families, seed_start, scenario_count, tags)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (name or f"{candidate} vs {baseline}", baseline, candidate, fams, seed_start, scenario_count,
         Jsonb(tags or {})),
    ).fetchone()
    return row["id"]


def get(conn: psycopg.Connection, campaign_id: int) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,)).fetchone()


def list_recent(conn: psycopg.Connection, limit: int = 50) -> list[dict[str, Any]]:
    return conn.execute("SELECT * FROM campaigns ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


class _Status:
    """Status/progress updates on their own autocommit connection, so they are
    visible while the long-running work happens elsewhere."""

    def __init__(self, url: str | None, campaign_id: int):
        self.conn = fgdb.connect(url, autocommit=True)
        self.id = campaign_id
        self._last = 0.0

    def set(self, status: str, **fields: Any) -> None:
        sets = ["status = %s"] + [f"{k} = %s" for k in fields]
        self.conn.execute(f"UPDATE campaigns SET {', '.join(sets)} WHERE id = %s",
                          (status, *fields.values(), self.id))

    def progress(self, done: int, total: int) -> None:
        now = time.monotonic()
        if done < total and now - self._last < 0.5:
            return
        self._last = now
        self.conn.execute("UPDATE campaigns SET progress = %s WHERE id = %s", (done / max(total, 1), self.id))

    def close(self) -> None:
        self.conn.close()


def run(campaign_id: int, *, url: str | None = None, sim: Fgsim | None = None, threads: int | None = None,
        runs_dir: Path | None = None, keep_files: bool = False,
        after_ingest: Callable[[psycopg.Connection, int], None] | None = None) -> dict[str, Any]:
    """Simulate, ingest and (optionally) post-process one campaign end to end."""
    settings = get_settings()
    sim = sim or Fgsim()
    status = _Status(url, campaign_id)
    out_dir = Path(runs_dir or settings.runs_dir) / f"campaign-{campaign_id}"
    try:
        with fgdb.session(url) as conn:
            c = get(conn, campaign_id)
            if c is None:
                raise CampaignError(f"no campaign {campaign_id}")
            rows = conn.execute("SELECT name, overrides FROM builds WHERE name = ANY(%s)",
                                ([c["baseline"], c["candidate"]],))
            builds = {r["name"]: r["overrides"] for r in rows}

        status.set("running", started_at=_now(), progress=0.0, error=None)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        stats = sim.batch(
            count=c["scenario_count"], out_dir=out_dir, families=c["families"], seed_start=c["seed_start"],
            baseline=builds[c["baseline"]], candidate=builds[c["candidate"]],
            threads=settings.sim_threads if threads is None else threads, on_progress=status.progress,
        )
        status.set("ingesting", progress=1.0, sim_seconds=stats["seconds"],
                   drives_per_second=stats["drives_per_second"])
        with fgdb.session(url) as conn:
            counts = ingest_batch(conn, campaign_id, out_dir)
        if after_ingest is not None:
            status.set("classifying")
            with fgdb.session(url) as conn:
                after_ingest(conn, campaign_id)
        status.set("done", finished_at=_now())
        return {"sim": stats, "ingested": counts}
    except Exception as exc:
        status.set("failed", error=f"{type(exc).__name__}: {exc}", finished_at=_now())
        raise
    finally:
        status.close()
        if not keep_files and out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)


def _now() -> datetime:
    return datetime.now(UTC)
