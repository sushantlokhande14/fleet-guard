"""Generate the provisioned Grafana dashboards (dashboards as code).

    python tools/gen_dashboards.py          # writes deploy/grafana/dashboards/*.json

Editing the JSON by hand works too, but regenerating keeps panel ids, grid
positions and datasource references consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "deploy" / "grafana" / "dashboards"
PROM = {"type": "prometheus", "uid": "prometheus"}
PG = {"type": "grafana-postgresql-datasource", "uid": "fleetdb"}


class Board:
    def __init__(self, uid: str, title: str, tags: list[str], description: str):
        self.d = {
            "uid": uid, "title": title, "tags": tags, "description": description, "editable": True,
            "schemaVersion": 39, "version": 1, "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
            "panels": [], "templating": {"list": []}, "annotations": {"list": []},
        }
        self._id = 0
        self._y = 0
        self._x = 0
        self._row_h = 0

    def var(self, name: str, label: str, query: str, ds: dict = PG) -> None:
        self.d["templating"]["list"].append({
            "name": name, "label": label, "type": "query", "datasource": ds, "query": query,
            "refresh": 1, "sort": 0, "includeAll": False, "multi": False,
        })

    def panel(self, title: str, kind: str, w: int, h: int, targets: list[dict], ds: dict,
              description: str = "", **extra) -> None:
        if self._x + w > 24:
            self._x = 0
            self._y += self._row_h
            self._row_h = 0
        self._id += 1
        p = {"id": self._id, "type": kind, "title": title, "description": description, "datasource": ds,
             "gridPos": {"x": self._x, "y": self._y, "w": w, "h": h}, "targets": targets}
        p.update(extra)
        self.d["panels"].append(p)
        self._x += w
        self._row_h = max(self._row_h, h)

    def row(self, title: str) -> None:
        self._x = 0
        self._y += self._row_h
        self._row_h = 1
        self._id += 1
        self.d["panels"].append({"id": self._id, "type": "row", "title": title, "collapsed": False,
                                 "gridPos": {"x": 0, "y": self._y, "w": 24, "h": 1}, "panels": []})
        self._x = 24  # force the next panel onto a new line

    def write(self) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{self.d['uid']}.json"
        path.write_text(json.dumps(self.d, indent=2) + "\n")
        return path


def prom(expr: str, legend: str = "", instant: bool = False, ref: str = "A") -> dict:
    t = {"datasource": PROM, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t.update({"instant": True, "range": False, "format": "table"})
    return t


def sql(query: str, ref: str = "A", fmt: str = "table") -> dict:
    return {"datasource": PG, "rawSql": query.strip(), "format": fmt, "rawQuery": True, "editorMode": "code",
            "refId": ref}


def stat_opts(unit: str = "none", decimals: int | None = None, thresholds: list | None = None) -> dict:
    defaults = {"unit": unit}
    if decimals is not None:
        defaults["decimals"] = decimals
    if thresholds:
        defaults["thresholds"] = {"mode": "absolute", "steps": thresholds}
        defaults["color"] = {"mode": "thresholds"}
    else:
        # informational numbers: no traffic-light colour
        defaults["color"] = {"mode": "fixed", "fixedColor": "text"}
    return {"fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none"}}


GREEN_RED = [{"color": "green", "value": None}, {"color": "red", "value": 1}]


def overview() -> Board:
    b = Board("fleetguard-overview", "Fleet Guard / Overview", ["fleetguard"],
              "Campaign queue, worker throughput and the regression status of every candidate build.")
    b.panel("Regressed candidates", "stat", 4, 4, [prom("count(fleetguard_campaign_regression == 1) or vector(0)")],
            PROM, "Candidate builds whose latest campaign was judged a regression.", **stat_opts(thresholds=GREEN_RED))
    b.panel("Queued", "stat", 4, 4, [prom('fleetguard_campaigns{status="queued"}')], PROM, **stat_opts())
    b.panel("Running", "stat", 4, 4,
            [prom('sum(fleetguard_campaigns{status=~"running|ingesting|classifying"})')], PROM, **stat_opts())
    b.panel("Failed campaigns", "stat", 4, 4, [prom('fleetguard_campaigns{status="failed"}')], PROM,
            **stat_opts(thresholds=GREEN_RED))
    b.panel("Drives stored", "stat", 4, 4, [prom("fleetguard_drives_stored")], PROM, **stat_opts(unit="short"))
    b.panel("Database", "stat", 4, 4, [prom("fleetguard_db_up")], PROM, "1 = exporter can read Postgres",
            **stat_opts(thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}]))

    b.row("Latest campaign per candidate")
    b.panel("Disengagements per 1000 km", "bargauge", 12, 8,
            [prom("fleetguard_build_disengagements_per_1000km", "{{candidate}} {{role}}", instant=False)], PROM,
            "Takeovers and collisions per 1000 km, baseline vs candidate, from each candidate's latest campaign.",
            options={"orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}})
    b.panel("Planner p99 latency (ms)", "bargauge", 12, 8,
            [prom("fleetguard_build_planner_p99_ms", "{{candidate}} {{role}}")], PROM,
            "99th percentile over drives of per-drive planner p99. Budget is 100 ms.",
            fieldConfig={"defaults": {"unit": "ms", "max": 120, "thresholds": {"mode": "absolute", "steps": [
                {"color": "green", "value": None}, {"color": "orange", "value": 80}, {"color": "red", "value": 90}]},
                "color": {"mode": "thresholds"}}, "overrides": []},
            options={"orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}})
    b.panel("Failures by category", "bargauge", 12, 8,
            [prom("fleetguard_campaign_failures > 0", "{{candidate}} {{category}}")], PROM,
            options={"orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}})
    b.panel("Perception recall", "bargauge", 12, 8,
            [prom("fleetguard_build_perception_recall", "{{candidate}} {{role}}")], PROM,
            fieldConfig={"defaults": {"unit": "percentunit", "min": 0.9, "max": 1, "decimals": 3}, "overrides": []},
            options={"orientation": "horizontal", "reduceOptions": {"calcs": ["lastNotNull"]}})

    b.row("Worker")
    b.panel("Simulation throughput", "timeseries", 12, 8,
            [prom("fleetguard_worker_sim_drives_per_second", "{{instance}}")], PROM,
            fieldConfig={"defaults": {"unit": "short", "custom": {"drawStyle": "line"}}, "overrides": []})
    b.panel("Campaign wall time", "timeseries", 12, 8,
            [prom("histogram_quantile(0.5, sum by (le) (rate(fleetguard_worker_campaign_seconds_bucket[30m])))",
                  "p50"),
             prom("histogram_quantile(0.95, sum by (le) (rate(fleetguard_worker_campaign_seconds_bucket[30m])))",
                  "p95", ref="B")], PROM, fieldConfig={"defaults": {"unit": "s"}, "overrides": []})
    b.panel("Firing alerts", "alertlist", 24, 6, [], PROM,
            options={"alertListOptions": {"showOptions": "current"}, "stateFilter": {"firing": True, "pending": True}})
    return b


def build_comparison() -> Board:
    b = Board("fleetguard-campaign", "Fleet Guard / Build comparison", ["fleetguard"],
              "One campaign: baseline vs candidate KPIs, failures by category and family, top clusters.")
    b.var("campaign", "Campaign",
          "SELECT id AS __value, '#' || id || '  ' || name AS __text FROM campaigns "
          "WHERE status = 'done' ORDER BY id DESC")
    b.panel("Verdict", "stat", 6, 4, [sql("SELECT upper(verdict->>'status') AS verdict FROM campaigns "
                                         "WHERE id = $campaign")], PG,
            fieldConfig={"defaults": {"mappings": [
                {"type": "value", "options": {"PASS": {"color": "green"}, "REGRESSION": {"color": "red"}}}],
                "color": {"mode": "fixed"}}, "overrides": []},
            options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/"}, "colorMode": "background"})
    b.panel("Failing scenarios", "stat", 6, 4,
            [sql("SELECT count(*) AS failures FROM failures WHERE campaign_id = $campaign")], PG, **stat_opts())
    b.panel("Drives", "stat", 6, 4, [sql("SELECT count(*) AS drives FROM drives WHERE campaign_id = $campaign")], PG,
            **stat_opts(unit="short"))
    b.panel("Simulation rate", "stat", 6, 4,
            [sql("SELECT drives_per_second FROM campaigns WHERE id = $campaign")], PG, **stat_opts(decimals=0))

    b.panel("Baseline vs candidate", "table", 24, 6, [sql("""
        SELECT role, build, drives, completed, disengaged, collisions, timeouts,
               round(km::numeric, 1) AS km,
               round(disengagements_per_1000km::numeric, 2) AS "dis/1000km",
               round(recall::numeric, 4) AS recall, round(precision::numeric, 4) AS precision,
               round(planner_p99_p99_ms::numeric, 1) AS "planner p99 (ms)",
               deadline_misses AS "deadline misses",
               round(cte_p95_mean::numeric, 3) AS "cte p95 (m)",
               round(steer_reversal_rate::numeric, 3) AS "steer rev/s",
               round(accel_reversal_rate::numeric, 3) AS "accel rev/s"
          FROM campaign_role_metrics WHERE campaign_id = $campaign ORDER BY role
    """)], PG)

    b.panel("Failures by category", "barchart", 12, 8, [sql("""
        SELECT category, count(*) AS failures FROM failures WHERE campaign_id = $campaign
         GROUP BY category ORDER BY failures DESC
    """)], PG, options={"orientation": "horizontal", "xField": "category"})
    b.panel("Failures by family", "barchart", 12, 8, [sql("""
        SELECT s.family, count(*) AS failures FROM failures f JOIN scenarios s ON s.id = f.scenario_id
         WHERE f.campaign_id = $campaign GROUP BY s.family ORDER BY failures DESC
    """)], PG, options={"orientation": "horizontal", "xField": "family"})

    b.panel("Top clusters", "table", 12, 9, [sql("""
        SELECT signature, count(*) AS failures, max(severity) AS severity,
               round(avg(score)::numeric, 2) AS "mean score"
          FROM failures WHERE campaign_id = $campaign
         GROUP BY signature ORDER BY failures DESC LIMIT 15
    """)], PG)
    b.panel("Per family", "table", 12, 9, [sql("""
        SELECT family, role, drives, failed, collisions, round(recall::numeric, 4) AS recall,
               round(planner_p99_p99_ms::numeric, 1) AS "planner p99",
               round(steer_reversal_rate::numeric, 3) AS "steer rev/s"
          FROM campaign_family_metrics WHERE campaign_id = $campaign ORDER BY family, role
    """)], PG)
    b.panel("Strongest failures", "table", 24, 9, [sql("""
        SELECT f.id, f.scenario_id, f.category, f.severity, round(f.score::numeric, 2) AS score,
               round(f.first_t::numeric, 1) AS "first at (s)", array_to_string(f.secondary, ', ') AS also,
               f.repro_verified AS reproduced
          FROM failures f WHERE f.campaign_id = $campaign ORDER BY f.severity DESC, f.score DESC LIMIT 25
    """)], PG)
    return b


def failure_telemetry() -> Board:
    b = Board("fleetguard-failure", "Fleet Guard / Failure telemetry", ["fleetguard"],
              "10 Hz telemetry of one failing scenario, baseline against candidate on the same clock.")
    b.var("campaign", "Campaign",
          "SELECT id AS __value, '#' || id || '  ' || name AS __text FROM campaigns "
          "WHERE status = 'done' ORDER BY id DESC")
    b.var("failure", "Failure",
          "SELECT f.id AS __value, f.scenario_id || '  ' || f.category AS __text FROM failures f "
          "JOIN pairs p ON p.campaign_id = f.campaign_id AND p.scenario_id = f.scenario_id "
          "WHERE f.campaign_id = $campaign AND EXISTS (SELECT 1 FROM telemetry_frames t "
          "WHERE t.drive_id = p.candidate_drive) ORDER BY f.severity DESC, f.score DESC")

    def series(col: str, title: str, unit: str, w: int = 12) -> None:
        q = f"""
        SELECT t.t AS "time (s)",
               max(t.{col}) FILTER (WHERE d.role = 'baseline')  AS baseline,
               max(t.{col}) FILTER (WHERE d.role = 'candidate') AS candidate
          FROM failures f
          JOIN pairs p ON p.campaign_id = f.campaign_id AND p.scenario_id = f.scenario_id
          JOIN drives d ON d.id IN (p.baseline_drive, p.candidate_drive)
          JOIN telemetry_frames t ON t.drive_id = d.id
         WHERE f.id = $failure
         GROUP BY t.t ORDER BY t.t
        """
        b.panel(title, "trend", w, 8, [sql(q)], PG,
                fieldConfig={"defaults": {"unit": unit, "custom": {"lineWidth": 2, "spanNulls": True}},
                             "overrides": [{"matcher": {"id": "byName", "options": "candidate"},
                                            "properties": [{"id": "color", "value": {"mode": "fixed",
                                                                                     "fixedColor": "red"}}]},
                                           {"matcher": {"id": "byName", "options": "time (s)"},
                                            "properties": [{"id": "unit", "value": "s"}]}]},
                options={"xField": "time (s)"})

    b.panel("Failure", "table", 24, 4, [sql("""
        SELECT f.scenario_id, f.category, f.signature, f.severity, round(f.first_t::numeric, 1) AS "first at (s)",
               array_to_string(f.secondary, ', ') AS also, f.evidence::text AS evidence
          FROM failures f WHERE f.id = $failure
    """)], PG)
    series("v", "Speed", "velocityms")
    series("cte", "Cross-track error", "lengthm")
    series("steer", "Road-wheel angle", "radian")
    series("a", "Acceleration", "accMS2")
    series("planner_latency_ms", "Planner cycle latency", "ms")
    series("gt_gap", "True gap to object ahead", "lengthm")
    series("n_missed", "Relevant objects without a track", "none")
    series("ttc", "Time to collision", "s")
    return b


def main() -> None:
    for board in (overview(), build_comparison(), failure_telemetry()):
        print("wrote", board.write())


if __name__ == "__main__":
    main()
