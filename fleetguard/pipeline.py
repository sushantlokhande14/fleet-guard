"""What happens to a campaign after its drives are ingested."""

from __future__ import annotations

import psycopg

from . import classifiers, verdict


def post_process(conn: psycopg.Connection, campaign_id: int) -> dict:
    failures = classifiers.classify_campaign(conn, campaign_id)
    v = verdict.store(conn, campaign_id)
    return {"failures": len(failures), "verdict": v}
