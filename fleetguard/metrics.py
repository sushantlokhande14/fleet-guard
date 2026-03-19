"""Prometheus metrics.

Two kinds:
  * process metrics for the worker (campaigns run, drives simulated, durations)
  * FleetCollector, which reads fleet KPIs from Postgres at scrape time: queue
    depth, progress of running campaigns, and for the latest finished campaign
    of each candidate build its disengagement rate, recall, planner latency,
    failures per category and the regression verdict. Alert rules key off these.
"""

from __future__ import annotations

import logging

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily

from . import db as fgdb
from .classifiers import CATEGORIES

log = logging.getLogger("fleetguard.metrics")

# --- worker process metrics -------------------------------------------------------

WORKER_REGISTRY = CollectorRegistry()
CAMPAIGNS_RUN = Counter("fleetguard_worker_campaigns_total", "Campaigns finished by this worker",
                        ["status"], registry=WORKER_REGISTRY)
DRIVES_SIMULATED = Counter("fleetguard_worker_drives_simulated_total", "Drives simulated by this worker",
                           registry=WORKER_REGISTRY)
CAMPAIGN_SECONDS = Histogram("fleetguard_worker_campaign_seconds", "Wall time per campaign (sim + ingest + classify)",
                             buckets=(1, 2, 5, 10, 20, 40, 80, 160, 320, 640), registry=WORKER_REGISTRY)
SIM_RATE = Gauge("fleetguard_worker_sim_drives_per_second", "Simulation throughput of the last campaign",
                 registry=WORKER_REGISTRY)
BUSY = Gauge("fleetguard_worker_busy", "1 while a campaign is running", registry=WORKER_REGISTRY)
LAST_SUCCESS = Gauge("fleetguard_worker_last_success_timestamp_seconds", "Unix time of the last finished campaign",
                     registry=WORKER_REGISTRY)


# --- fleet KPIs straight from the database ------------------------------------------

ROLE_KPIS = {
    "disengagements_per_1000km": ("fleetguard_build_disengagements_per_1000km",
                                  "Takeovers and collisions per 1000 km"),
    "recall": ("fleetguard_build_perception_recall", "Share of relevant objects the tracker reported"),
    "planner_p99_p99_ms": ("fleetguard_build_planner_p99_ms", "99th percentile over drives of planner p99 latency"),
    "steer_reversal_rate": ("fleetguard_build_steer_reversal_rate", "Mean steering reversals per second"),
    "cte_p95_mean": ("fleetguard_build_cte_p95_m", "Mean 95th percentile cross-track error"),
    "hard_brakes_per_100km": ("fleetguard_build_hard_brakes_per_100km", "Hard-brake episodes per 100 km"),
}


class FleetCollector:
    def __init__(self, url: str | None = None):
        self.url = url

    def collect(self):
        up = GaugeMetricFamily("fleetguard_db_up", "1 if the exporter could read the database")
        try:
            families = self._collect()
        except Exception as exc:  # a scrape must never raise
            log.warning("fleet metrics unavailable: %s", exc)
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up
        yield from families

    def _collect(self) -> list:
        out = []
        with fgdb.session(self.url) as conn:
            by_status = GaugeMetricFamily("fleetguard_campaigns", "Campaigns by status", labels=["status"])
            counts = {r["status"]: r["n"] for r in conn.execute(
                "SELECT status, count(*) AS n FROM campaigns GROUP BY status")}
            for status in ("queued", "running", "ingesting", "classifying", "done", "failed"):
                by_status.add_metric([status], counts.get(status, 0))
            out.append(by_status)

            progress = GaugeMetricFamily("fleetguard_campaign_progress", "Simulation progress of active campaigns",
                                         labels=["campaign", "candidate"])
            for r in conn.execute("SELECT id, candidate, progress FROM campaigns "
                                  "WHERE status IN ('running', 'ingesting', 'classifying')"):
                progress.add_metric([str(r["id"]), r["candidate"]], r["progress"])
            out.append(progress)

            drives = GaugeMetricFamily("fleetguard_drives_stored", "Drives stored in the database")
            drives.add_metric([], conn.execute("SELECT count(*) AS n FROM drives").fetchone()["n"])
            out.append(drives)

            latest = conn.execute(
                """
                SELECT DISTINCT ON (candidate) id, candidate, baseline, verdict
                  FROM campaigns
                 WHERE status = 'done' AND NOT (tags ? 'benchmark')
                 ORDER BY candidate, finished_at DESC
                """
            ).fetchall()
            kpis = {k: GaugeMetricFamily(name, doc, labels=["campaign", "build", "role", "candidate"])
                    for k, (name, doc) in ROLE_KPIS.items()}
            failures = GaugeMetricFamily("fleetguard_campaign_failures", "Classified failures in the latest campaign",
                                         labels=["campaign", "candidate", "baseline", "category"])
            regression = GaugeMetricFamily("fleetguard_campaign_regression",
                                           "1 if the latest campaign of a candidate build was judged a regression",
                                           labels=["campaign", "candidate", "baseline"])
            for c in latest:
                cid = str(c["id"])
                for r in conn.execute("SELECT * FROM campaign_role_metrics WHERE campaign_id = %s", (c["id"],)):
                    for k, fam in kpis.items():
                        if r[k] is not None:
                            fam.add_metric([cid, r["build"], r["role"], c["candidate"]], float(r[k]))
                v = c["verdict"] or {}
                cats = v.get("categories", {})
                for cat in CATEGORIES:
                    failures.add_metric([cid, c["candidate"], c["baseline"], cat],
                                        cats.get(cat, {}).get("failures", 0))
                regression.add_metric([cid, c["candidate"], c["baseline"]],
                                      1 if v.get("status") == "regression" else 0)
            out += [*kpis.values(), failures, regression]
        return out


def fleet_registry(url: str | None = None) -> CollectorRegistry:
    reg = CollectorRegistry()
    reg.register(FleetCollector(url))
    return reg
