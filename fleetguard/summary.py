"""Campaign summary as markdown, for a PR comment or a CI job summary."""

from __future__ import annotations

from typing import Any

import psycopg

from .classifiers import CATEGORIES

KPIS = [
    ("disengagements_per_1000km", "disengagements / 1000 km", 2),
    ("recall", "perception recall", 4),
    ("planner_p99_p99_ms", "planner p99 (ms)", 1),
    ("steer_reversal_rate", "steering reversals / s", 3),
    ("cte_p95_mean", "p95 cross-track error (m)", 3),
]


def _f(v: Any, nd: int) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


def campaign_markdown(conn: psycopg.Connection, campaign_id: int, ui_base: str | None = None) -> str:
    c = conn.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,)).fetchone()
    if c is None:
        raise LookupError(f"no campaign {campaign_id}")
    v = c["verdict"]
    base = ui_base.rstrip("/") if ui_base else None
    cid = c["id"]
    head = f"[#{cid}]({base}/campaigns/{cid})" if base else f"#{cid}"
    if v is None:
        return f"## Fleet Guard {head}: {c['candidate']} vs {c['baseline']}\n\nStatus: {c['status']}\n"

    mark = "PASS" if v["status"] == "pass" else "REGRESSION"
    out = [
        f"## Fleet Guard {head}: {c['candidate']} vs {c['baseline']}: **{mark}**",
        "",
        f"{c['scenario_count']:,} scenarios x 2 builds = {2 * c['scenario_count']:,} drives, "
        f"{v['failures']} failing scenarios.",
        "",
        "| category | failures | per 1000 scenarios | flagged |",
        "|---|---|---|---|",
    ]
    for cat in CATEGORIES:
        row = v["categories"][cat]
        out.append(f"| {cat} | {row['failures']} | {row['per_1000']} | {'yes' if row['flagged'] else ''} |")

    roles = {r["role"]: r for r in conn.execute(
        "SELECT * FROM campaign_role_metrics WHERE campaign_id = %s", (campaign_id,))}
    if "baseline" in roles and "candidate" in roles:
        out += ["", "| KPI | baseline | candidate |", "|---|---|---|"]
        for key, name, nd in KPIS:
            out.append(f"| {name} | {_f(roles['baseline'][key], nd)} | {_f(roles['candidate'][key], nd)} |")

    clusters = conn.execute(
        """
        SELECT signature, count(*) AS n, (array_agg(id ORDER BY score DESC))[1] AS example
          FROM failures WHERE campaign_id = %s GROUP BY signature ORDER BY n DESC, signature LIMIT 5
        """,
        (campaign_id,),
    ).fetchall()
    if clusters:
        out += ["", "Top clusters (one probable bug each):", ""]
        for cl in clusters:
            fid = cl["example"]
            ex = f"[failure #{fid}]({base}/failures/{fid})" if base else f"failure #{fid}"
            out.append(f"- `{cl['signature']}`: {cl['n']} ({ex})")
        out += ["", "Every failure replays exactly: `fleetguard repro <failure id>`."]
    return "\n".join(out) + "\n"
