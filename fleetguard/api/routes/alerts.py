from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from ..deps import Conn

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AMAlert(BaseModel):
    status: str
    labels: dict[str, str]
    annotations: dict[str, str] = {}
    startsAt: datetime
    endsAt: str | None = None
    fingerprint: str


class AMWebhook(BaseModel):
    """Alertmanager webhook payload (version 4); only the fields we use."""
    status: str
    alerts: list[AMAlert]


@router.post("/webhook")
def webhook(body: AMWebhook, conn: Conn) -> dict:
    for a in body.alerts:
        campaign = a.labels.get("campaign")
        campaign_id = int(campaign) if campaign and campaign.isdigit() else None
        if campaign_id is not None and conn.execute("SELECT 1 FROM campaigns WHERE id = %s",
                                                    (campaign_id,)).fetchone() is None:
            campaign_id = None
        # Alertmanager sends 0001-01-01T00:00:00Z for alerts that have not ended
        ends = None if not a.endsAt or a.endsAt.startswith("0001") else a.endsAt
        conn.execute(
            """
            INSERT INTO alerts (fingerprint, alertname, status, severity, campaign_id, labels, annotations,
                                starts_at, ends_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fingerprint) DO UPDATE
               SET status = EXCLUDED.status, annotations = EXCLUDED.annotations,
                   ends_at = EXCLUDED.ends_at, updated_at = now()
            """,
            (a.fingerprint, a.labels.get("alertname", "unknown"), a.status, a.labels.get("severity"), campaign_id,
             Jsonb(a.labels), Jsonb(a.annotations), a.startsAt, ends),
        )
    return {"received": len(body.alerts)}


@router.get("")
def list_alerts(conn: Conn, status: str | None = "firing", limit: int = 100) -> list[dict]:
    return conn.execute(
        """
        SELECT fingerprint, alertname, status, severity, campaign_id, labels, annotations, starts_at, ends_at
          FROM alerts WHERE (%(s)s::text IS NULL OR status = %(s)s)
         ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, starts_at DESC
         LIMIT %(n)s
        """,
        {"s": status, "n": min(limit, 500)},
    ).fetchall()
