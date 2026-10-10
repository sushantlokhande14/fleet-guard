"""Failure classification.

Five SQL classifiers (sql/*.sql) each look at every scenario pair of a campaign
and emit a signal when the candidate build is worse than the baseline in their
dimension. A scenario can fire several: a missed pedestrian leads to a late
brake leads to a takeover. Attribution picks the root cause by time: the
earliest timed signal at or before the disengagement wins.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

CLASSIFIER_VERSION = "2026.03"
CATEGORIES = ("disengagement", "latency_spike", "route_deviation", "perception_error", "control_instability")

# tie-break when two causes start at the same instant: upstream modules first
PRECEDENCE = {"perception_error": 0, "latency_spike": 1, "control_instability": 2, "route_deviation": 3,
              "disengagement": 4}

THRESHOLDS: dict[str, float] = {
    "latency_min_new_misses": 2,
    "latency_p99_floor_ms": 70.0,
    "latency_p99_delta_ms": 12.0,
    "latency_min_new_events": 2,
    "route_cte_floor_m": 0.45,
    "route_cte_delta_m": 0.25,
    "route_lat_diff_m": 0.4,
    "perc_recall_drop": 0.03,
    "perc_precision_drop": 0.05,
    "ctrl_steer_rev_delta": 0.15,
    "ctrl_accel_rev_delta": 0.25,
    "ctrl_rev_with_event": 0.08,
    "ctrl_jerk_delta": 0.6,
}

# an untimed (metric-only) signal can explain a disengagement only if it is strong
UNTIMED_CAUSE_MIN_SCORE = 0.5

SQL_DIR = Path(__file__).parent / "sql"


@dataclass
class Signal:
    scenario_id: str
    category: str
    score: float
    first_t: float | None
    evidence: dict[str, Any]


@dataclass
class Failure:
    scenario_id: str
    category: str
    severity: int
    score: float
    first_t: float | None
    evidence: dict[str, Any]
    secondary: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)
    signature: str = ""


def load_queries() -> dict[str, str]:
    return {c: (SQL_DIR / f"{c}.sql").read_text() for c in CATEGORIES}


def collect_signals(conn: psycopg.Connection, campaign_id: int,
                    thresholds: dict[str, float] | None = None) -> list[Signal]:
    params = {"campaign": campaign_id, **THRESHOLDS, **(thresholds or {})}
    out = []
    for category, sql in load_queries().items():
        for r in conn.execute(sql, params):
            out.append(Signal(r["scenario_id"], category, float(r["score"]),
                              None if r["first_t"] is None else float(r["first_t"]), r["evidence"]))
    return out


def _order(s: Signal) -> tuple:
    return (s.first_t if s.first_t is not None else float("inf"), PRECEDENCE[s.category], -s.score)


def attribute(signals: list[Signal]) -> Failure:
    """Pick the root-cause category for one scenario's signals."""
    dis = next((s for s in signals if s.category == "disengagement"), None)
    others = [s for s in signals if s.category != "disengagement"]
    if dis is not None:
        t_end = dis.first_t if dis.first_t is not None else float("inf")
        causes = [s for s in others if s.first_t is not None and s.first_t <= t_end + 0.5]
        if not causes:
            causes = [s for s in others if s.first_t is None and s.score >= UNTIMED_CAUSE_MIN_SCORE]
        primary = min(causes, key=_order) if causes else dis
        severity = 3
    else:
        timed = [s for s in others if s.first_t is not None]
        primary = min(timed, key=_order) if timed else max(others, key=lambda s: s.score)
        severity = 2 if timed else 1
    secondary = sorted({s.category for s in signals if s is not primary}, key=PRECEDENCE.get)
    return Failure(
        scenario_id=primary.scenario_id,
        category=primary.category,
        severity=severity,
        score=round(primary.score, 4),
        first_t=primary.first_t,
        evidence=primary.evidence,
        secondary=secondary,
        signals={s.category: {"score": round(s.score, 4), "first_t": s.first_t, "evidence": s.evidence}
                 for s in signals},
    )


def signature(f: Failure, family: str) -> str:
    """Cluster key: failures with the same signature are very likely one bug."""
    ev = f.evidence
    if f.category == "disengagement":
        key = ev.get("reason") or ev.get("outcome") or "unknown"
        detail = (ev.get("detail") or "").split()
        if len(detail) >= 2 and key == "ttc_takeover":
            key += f":{detail[1]}"  # ttc_takeover vehicle 1 -> ttc_takeover:vehicle
    elif f.category == "perception_error":
        misses = ev.get("new_misses") or []
        if misses:
            key = misses[0]["object"].split()[0]
        else:
            key = "phantom" if ev.get("new_phantoms") else "recall"
    elif f.category == "latency_spike":
        base_misses, cand_misses = ev["deadline_misses"]
        if ev.get("watchdog"):
            key = "watchdog"
        else:
            key = "deadline" if cand_misses > base_misses else "p99"
    elif f.category == "route_deviation":
        key = "lane_departure" if ev.get("lane_departure") else "offset"
    else:
        axes = ev.get("axes") or []
        key = "+".join(sorted(a.split("_")[0] for a in axes)) if axes else "reversals"
    return f"{f.category}/{family}/{key}"


def classify_campaign(conn: psycopg.Connection, campaign_id: int,
                      thresholds: dict[str, float] | None = None) -> list[Failure]:
    """Classify every scenario pair of a campaign and (re)write its failures."""
    by_scenario: dict[str, list[Signal]] = defaultdict(list)
    for s in collect_signals(conn, campaign_id, thresholds):
        by_scenario[s.scenario_id].append(s)
    rows = conn.execute(
        "SELECT s.id, s.family FROM pairs p JOIN scenarios s ON s.id = p.scenario_id"
        " WHERE p.campaign_id = %s",
        (campaign_id,))
    families = {r["id"]: r["family"] for r in rows}

    failures = []
    for sid in sorted(by_scenario):
        f = attribute(by_scenario[sid])
        f.signature = signature(f, families[sid])
        failures.append(f)

    conn.execute("DELETE FROM failures WHERE campaign_id = %s", (campaign_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO failures (campaign_id, scenario_id, category, secondary, severity, score, first_t,
                                  signature, evidence, signals, classifier_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(campaign_id, f.scenario_id, f.category, f.secondary, f.severity, f.score, f.first_t,
              f.signature, Jsonb(f.evidence), Jsonb(f.signals), CLASSIFIER_VERSION) for f in failures],
        )
    return failures
