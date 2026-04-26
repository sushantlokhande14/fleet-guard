"""What happens to a campaign after its drives are ingested."""

from __future__ import annotations

import os

import psycopg

from . import classifiers, verdict
from .diagnostics import report
from .diagnostics.llm import LLMClient


def auto_reports(conn: psycopg.Connection, campaign_id: int, max_clusters: int | None = None,
                 llm: LLMClient | None = None) -> list[int]:
    """One report per cluster (its strongest failure), biggest clusters first."""
    if max_clusters is None:
        max_clusters = int(os.environ.get("FG_AUTO_REPORTS", "10"))
    if max_clusters <= 0:
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT ON (signature) id, signature, n
          FROM (SELECT id, signature, score, severity,
                       count(*) OVER (PARTITION BY signature) AS n
                  FROM failures WHERE campaign_id = %s) f
         ORDER BY signature, severity DESC, score DESC
        """,
        (campaign_id,),
    ).fetchall()
    rows.sort(key=lambda r: (-r["n"], r["signature"]))
    return [report.generate(conn, r["id"], llm=llm)["id"] for r in rows[:max_clusters]]


def post_process(conn: psycopg.Connection, campaign_id: int) -> dict:
    failures = classifiers.classify_campaign(conn, campaign_id)
    v = verdict.store(conn, campaign_id)
    # LLM narratives take seconds each on a local model, so by default the worker
    # writes template reports and the UI asks for an LLM narrative on demand
    llm = LLMClient() if os.environ.get("FG_AUTO_REPORTS_LLM") == "1" else None
    try:
        reports = auto_reports(conn, campaign_id, llm=llm)
    finally:
        if llm is not None:
            llm.close()
    return {"failures": len(failures), "verdict": v, "reports": len(reports)}
