"""Campaign verdict: did the candidate regress, and in what?

A category is flagged when it has enough failures to stand out from noise, both
in absolute count and per 1,000 scenarios. The thresholds come from campaigns of
the baseline against itself and against benign changes (see docs/RESULTS.md).
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .classifiers import CATEGORIES

MIN_FAILURES = 3
MIN_PER_1000 = 5.0


def compute(conn: psycopg.Connection, campaign_id: int) -> dict[str, Any]:
    c = conn.execute("SELECT scenario_count FROM campaigns WHERE id = %s", (campaign_id,)).fetchone()
    n_scen = c["scenario_count"]
    rows = conn.execute(
        """
        SELECT category, count(*) AS n, count(*) FILTER (WHERE severity = 3) AS critical
        FROM failures WHERE campaign_id = %s GROUP BY category
        """,
        (campaign_id,),
    ).fetchall()
    found = {r["category"]: r for r in rows}
    categories = {}
    for cat in CATEGORIES:
        n = found[cat]["n"] if cat in found else 0
        per_1000 = 1000.0 * n / n_scen
        categories[cat] = {
            "failures": n,
            "critical": found[cat]["critical"] if cat in found else 0,
            "per_1000": round(per_1000, 2),
            "flagged": n >= MIN_FAILURES and per_1000 >= MIN_PER_1000,
        }
    flagged = sorted((c for c in CATEGORIES if categories[c]["flagged"]),
                     key=lambda c: -categories[c]["failures"])
    clusters = conn.execute(
        """
        SELECT signature, category, count(*) AS n, max(severity) AS severity
        FROM failures WHERE campaign_id = %s
        GROUP BY signature, category ORDER BY n DESC, signature LIMIT 10
        """,
        (campaign_id,),
    ).fetchall()
    return {
        "status": "regression" if flagged else "pass",
        "flagged": flagged,
        "top_category": flagged[0] if flagged else None,
        "scenarios": n_scen,
        "failures": sum(v["failures"] for v in categories.values()),
        "categories": categories,
        "top_clusters": [dict(r) for r in clusters],
        "thresholds": {"min_failures": MIN_FAILURES, "min_per_1000": MIN_PER_1000},
    }


def store(conn: psycopg.Connection, campaign_id: int) -> dict[str, Any]:
    v = compute(conn, campaign_id)
    conn.execute("UPDATE campaigns SET verdict = %s WHERE id = %s", (Jsonb(v), campaign_id))
    return v
