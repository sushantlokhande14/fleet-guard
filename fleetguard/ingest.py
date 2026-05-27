"""Load an fgsim batch output directory into Postgres.

Everything goes through COPY into temporary staging tables, then a set-based
INSERT ... SELECT resolves drive ids by (scenario, role). A 100k-drive campaign
ingests in seconds this way; row-by-row inserts would take minutes.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg

DRIVE_COLS = [
    "outcome", "reason", "duration_s", "distance_m", "route_completion", "mean_speed",
    "cte_max", "cte_rms", "cte_p95", "heading_err_max", "jerk_rms", "accel_min", "lat_acc_max",
    "steer_reversal_rate", "accel_reversal_rate", "min_ttc", "min_gap",
    "planner_p50_ms", "planner_p99_ms", "planner_max_ms", "planner_cycles", "deadline_misses",
    "det_tp", "det_fn", "det_fp", "recall", "precision", "hard_brakes", "n_events",
]

PAIR_COLS = [
    "common_s", "lat_mean_abs_diff", "lat_max_abs_diff", "speed_rmse", "time_delta_s",
    "first_divergence_s", "first_divergence_t", "outcome_changed",
    "d_cte_max", "d_jerk_rms", "d_steer_reversal_rate", "d_accel_reversal_rate", "d_min_ttc",
    "d_planner_p99_ms", "d_recall", "d_precision", "d_deadline_misses", "d_hard_brakes",
]

FRAME_COLS = [
    "t", "x", "y", "yaw", "v", "a", "steer", "steer_cmd", "accel_cmd", "s", "cte", "heading_err",
    "v_ref", "target_speed", "lead_id", "lead_gap", "gt_gap", "ttc", "planner_latency_ms",
    "deadline_miss", "n_tracks", "n_relevant", "n_missed", "n_phantom", "engaged",
]


def _jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def ingest_batch(conn: psycopg.Connection, campaign_id: int, out_dir: str | Path) -> dict[str, int]:
    out = Path(out_dir)
    counts: dict[str, int] = {}
    with conn.transaction(), conn.cursor() as cur:
        # -- scenarios (shared across campaigns) ------------------------------------
        cur.execute(
            "CREATE TEMP TABLE stage_scenarios (id text, family text, seed bigint, weather text,"
            " route_length_m real, speed_limit_mps real, params jsonb) ON COMMIT DROP"
        )
        with cur.copy("COPY stage_scenarios FROM STDIN") as cp:
            for d in _jsonl(out / "scenarios.jsonl"):
                cp.write_row((d["id"], d["family"], d["seed"], d["weather"], d["route_length_m"],
                              d["speed_limit_mps"], json.dumps(d)))
        cur.execute("INSERT INTO scenarios SELECT * FROM stage_scenarios ON CONFLICT (id) DO NOTHING")

        # -- drives ---------------------------------------------------------------
        cols = ", ".join(["campaign_id", "scenario_id", "role", "build", *DRIVE_COLS])
        n = 0
        with cur.copy(f"COPY drives ({cols}) FROM STDIN") as cp:
            for d in _jsonl(out / "drives.jsonl"):
                row = (campaign_id, d["scenario_id"], d["role"], d["build"], *[d[c] for c in DRIVE_COLS])
                cp.write_row(row)
                n += 1
        counts["drives"] = n
        # Temp tables never get statistics on their own, and the rows just copied
        # are invisible to the planner until analyzed. Without this the joins
        # below run as nested loops: a 50k-scenario campaign sat in the pairs
        # join for ten minutes.
        cur.execute("ANALYZE drives")

        # -- events ---------------------------------------------------------------
        cur.execute(
            "CREATE TEMP TABLE stage_events (scenario_id text, role text, t real, kind text,"
            " severity smallint, value real, duration real, detail text) ON COMMIT DROP"
        )
        with cur.copy("COPY stage_events FROM STDIN") as cp:
            for e in _jsonl(out / "events.jsonl"):
                cp.write_row((e["scenario_id"], e["role"], e["t"], e["kind"], e["severity"], e["value"],
                              e["duration"], e["detail"]))
        cur.execute("ANALYZE stage_events")
        cur.execute(
            """
            INSERT INTO drive_events (drive_id, t, kind, severity, value, duration, detail)
            SELECT d.id, e.t, e.kind, e.severity, e.value, e.duration, e.detail
              FROM stage_events e
              JOIN drives d ON d.campaign_id = %s AND d.scenario_id = e.scenario_id AND d.role = e.role
            """,
            (campaign_id,),
        )
        counts["events"] = cur.rowcount

        # -- pairs ----------------------------------------------------------------
        cur.execute(
            "CREATE TEMP TABLE stage_pairs (scenario_id text, flagged boolean, "
            + ", ".join(f"{c} {'boolean' if c == 'outcome_changed' else 'real'}" for c in PAIR_COLS)
            + ") ON COMMIT DROP"
        )
        with cur.copy("COPY stage_pairs FROM STDIN") as cp:
            for p in _jsonl(out / "pairs.jsonl"):
                cp.write_row((p["scenario_id"], p["flagged"], *[p[c] for c in PAIR_COLS]))
        cur.execute("ANALYZE stage_pairs")
        pair_cols = ", ".join(PAIR_COLS)
        cur.execute(
            f"""
            INSERT INTO pairs (campaign_id, scenario_id, baseline_drive, candidate_drive, flagged,
                               {pair_cols})
            SELECT %s, p.scenario_id, b.id, c.id, p.flagged, {", ".join("p." + c for c in PAIR_COLS)}
              FROM stage_pairs p
              JOIN drives b ON b.campaign_id = %s AND b.scenario_id = p.scenario_id AND b.role = 'baseline'
              JOIN drives c ON c.campaign_id = %s AND c.scenario_id = p.scenario_id AND c.role = 'candidate'
            """,
            (campaign_id, campaign_id, campaign_id),
        )
        counts["pairs"] = cur.rowcount

        # -- telemetry (CSV straight from fgsim) -----------------------------------
        frames = out / "frames.csv"
        counts["frames"] = 0
        if frames.exists():
            cur.execute(
                "CREATE TEMP TABLE stage_frames (scenario_id text, role text, "
                + ", ".join(f"{c} real" for c in FRAME_COLS)
                + ") ON COMMIT DROP"
            )
            with cur.copy("COPY stage_frames FROM STDIN WITH (FORMAT csv, HEADER true)") as cp, \
                    open(frames, "rb") as f:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
            cur.execute("ANALYZE stage_frames")
            frame_cols = ", ".join(FRAME_COLS)
            cur.execute(
                f"""
                INSERT INTO telemetry_frames (drive_id, {frame_cols})
                SELECT d.id, {", ".join("f." + c for c in FRAME_COLS)}
                  FROM stage_frames f
                  JOIN drives d ON d.campaign_id = %s AND d.scenario_id = f.scenario_id AND d.role = f.role
                """,
                (campaign_id,),
            )
            counts["frames"] = cur.rowcount

        # Fresh statistics for the classifiers too: without them the planner still
        # thinks this campaign has no rows and re-runs the event aggregates once
        # per pair (12.6 s instead of 48 ms on a 700-pair campaign).
        for table in ("scenarios", "drives", "drive_events", "pairs", "telemetry_frames"):
            cur.execute(f"ANALYZE {table}")
    return counts
