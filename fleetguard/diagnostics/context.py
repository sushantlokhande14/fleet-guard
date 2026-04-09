"""Collect every fact a report may state about one failure."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import psycopg

from .. import builds as fgbuilds
from .. import repro

# summary metrics shown side by side, with display names and units
KEY_METRICS = [
    ("outcome", "outcome", ""),
    ("reason", "end reason", ""),
    ("duration_s", "duration", "s"),
    ("route_completion", "route completed", ""),
    ("cte_max", "max cross-track error", "m"),
    ("cte_p95", "p95 cross-track error", "m"),
    ("min_ttc", "min time to collision", "s"),
    ("min_gap", "min gap", "m"),
    ("recall", "perception recall", ""),
    ("precision", "perception precision", ""),
    ("planner_p99_ms", "planner p99 latency", "ms"),
    ("deadline_misses", "planner deadline misses", ""),
    ("steer_reversal_rate", "steering reversals", "/s"),
    ("accel_reversal_rate", "accel reversals", "/s"),
    ("jerk_rms", "jerk RMS", "m/s^3"),
    ("hard_brakes", "hard brakes", ""),
]

TIMELINE_KINDS = ("disengagement", "collision", "perception_miss", "phantom_object", "latency_spike", "off_route",
                  "steer_oscillation", "accel_oscillation", "hard_brake")


@dataclass
class FailureContext:
    failure_id: int
    campaign_id: int
    campaign_name: str
    baseline: str
    candidate: str
    scenario: dict[str, Any]
    category: str
    secondary: list[str]
    severity: int
    score: float
    first_t: float | None
    signature: str
    evidence: dict[str, Any]
    signals: dict[str, Any]
    metrics: list[dict[str, Any]]
    pair: dict[str, Any]
    timeline: list[dict[str, Any]]
    build_diff: list[dict[str, Any]]
    cluster: dict[str, Any]
    repro_command: str
    repro_verified: bool | None
    extra: dict[str, Any] = field(default_factory=dict)

    def facts(self) -> dict[str, Any]:
        """Compact, JSON-serialisable view handed to the LLM and used by the guard."""
        d = asdict(self)
        d.pop("extra")
        return d


def _round(v: Any, nd: int = 3) -> Any:
    return round(v, nd) if isinstance(v, float) else v


def build_context(conn: psycopg.Connection, failure_id: int, timeline_limit: int = 40) -> FailureContext:
    f = conn.execute("SELECT * FROM failures WHERE id = %s", (failure_id,)).fetchone()
    if f is None:
        raise LookupError(f"no failure {failure_id}")
    c = conn.execute("SELECT id, name, baseline, candidate FROM campaigns WHERE id = %s",
                     (f["campaign_id"],)).fetchone()
    s = conn.execute("SELECT * FROM scenarios WHERE id = %s", (f["scenario_id"],)).fetchone()
    p = conn.execute("SELECT * FROM pairs WHERE campaign_id = %s AND scenario_id = %s",
                     (f["campaign_id"], f["scenario_id"])).fetchone()
    b = conn.execute("SELECT * FROM drives WHERE id = %s", (p["baseline_drive"],)).fetchone()
    k = conn.execute("SELECT * FROM drives WHERE id = %s", (p["candidate_drive"],)).fetchone()

    metrics = [{"key": key, "name": name, "unit": unit, "baseline": _round(b[key]), "candidate": _round(k[key])}
               for key, name, unit in KEY_METRICS]

    events = conn.execute(
        """
        SELECT CASE WHEN e.drive_id = %(b)s THEN 'baseline' ELSE 'candidate' END AS role,
               round(e.t::numeric, 2)::float AS t, e.kind, e.severity, round(e.value::numeric, 2)::float AS value,
               round(e.duration::numeric, 2)::float AS duration, e.detail
          FROM drive_events e
         WHERE e.drive_id IN (%(b)s, %(c)s) AND e.kind = ANY(%(kinds)s)
         ORDER BY e.t, role
        """,
        {"b": p["baseline_drive"], "c": p["candidate_drive"], "kinds": list(TIMELINE_KINDS)},
    ).fetchall()
    # keep the story readable: drop routine latency jitter that both builds share
    timeline = [e for e in events if not (e["kind"] == "latency_spike" and e["severity"] < 2)][:timeline_limit]

    params = {r["name"]: r["params"] for r in conn.execute(
        "SELECT name, params FROM builds WHERE name = ANY(%s)", ([c["baseline"], c["candidate"]],))}
    diff = [ch.as_dict() for ch in fgbuilds.diff(params[c["baseline"]], params[c["candidate"]])]

    cl = conn.execute(
        """
        SELECT count(*) AS size, array_agg(DISTINCT s.family) AS families,
               count(*) FILTER (WHERE f.severity = 3) AS critical
          FROM failures f JOIN scenarios s ON s.id = f.scenario_id
         WHERE f.campaign_id = %s AND f.signature = %s
        """,
        (f["campaign_id"], f["signature"]),
    ).fetchone()
    total = conn.execute("SELECT count(*) AS n FROM failures WHERE campaign_id = %s",
                         (f["campaign_id"],)).fetchone()["n"]

    params_summary = {k_: s["params"].get(k_) for k_ in ("speed_limit_mps", "ego_v0_mps", "friction", "cones")
                      if k_ in s["params"]}
    return FailureContext(
        failure_id=f["id"],
        campaign_id=c["id"],
        campaign_name=c["name"],
        baseline=c["baseline"],
        candidate=c["candidate"],
        scenario={"id": s["id"], "family": s["family"], "seed": s["seed"], "weather": s["weather"],
                  "route_length_m": round(s["route_length_m"], 1), **params_summary,
                  "actors": s["params"].get("actors", [])},
        category=f["category"],
        secondary=f["secondary"],
        severity=f["severity"],
        score=round(f["score"], 3),
        first_t=None if f["first_t"] is None else round(f["first_t"], 2),
        signature=f["signature"],
        evidence=f["evidence"],
        signals={k_: {"score": v["score"], "first_t": v["first_t"]} for k_, v in f["signals"].items()},
        metrics=metrics,
        pair={k_: _round(p[k_]) for k_ in ("lat_max_abs_diff", "speed_rmse", "time_delta_s", "first_divergence_s",
                                          "first_divergence_t", "outcome_changed")},
        timeline=timeline,
        build_diff=diff,
        cluster={"signature": f["signature"], "size": cl["size"], "families": sorted(cl["families"]),
                 "critical": cl["critical"], "campaign_failures": total},
        repro_command=repro.command(repro.load_case(conn, failure_id)),
        repro_verified=f["repro_verified"],
    )
