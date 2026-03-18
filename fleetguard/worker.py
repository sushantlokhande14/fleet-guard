"""Campaign worker: claims queued campaigns and runs them.

Several workers can share one database; each claim is a single UPDATE over a
FOR UPDATE SKIP LOCKED subquery, so two workers never pick the same campaign
and neither blocks on the other's lock.
"""

from __future__ import annotations

import logging
import signal
import threading
import time

import psycopg

from . import campaigns
from . import db as fgdb
from .config import get_settings
from .pipeline import post_process
from .sim import Fgsim

log = logging.getLogger("fleetguard.worker")

CLAIM_SQL = """
UPDATE campaigns SET status = 'running', started_at = now()
 WHERE id = (SELECT id FROM campaigns
              WHERE status = 'queued'
              ORDER BY created_at, id
              FOR UPDATE SKIP LOCKED
              LIMIT 1)
RETURNING id
"""


def claim_next(conn: psycopg.Connection) -> int | None:
    row = conn.execute(CLAIM_SQL).fetchone()
    conn.commit()
    return row["id"] if row else None


class Worker:
    def __init__(self, url: str | None = None, sim: Fgsim | None = None, poll_s: float = 2.0):
        self.url = url or get_settings().database_url
        self.sim = sim or Fgsim()
        self.poll_s = poll_s
        self.stop = threading.Event()

    def run_one(self) -> int | None:
        """Claim and run one campaign. Returns its id, or None if the queue was empty."""
        conn = fgdb.connect(self.url)
        try:
            cid = claim_next(conn)
        finally:
            conn.close()
        if cid is None:
            return None
        log.info("campaign %s: starting", cid)
        try:
            campaigns.run(cid, url=self.url, sim=self.sim, after_ingest=post_process)
            log.info("campaign %s: done", cid)
        except Exception:
            # campaigns.run already recorded status=failed and the error text
            log.exception("campaign %s: failed", cid)
        return cid

    def loop(self) -> None:
        log.info("worker polling every %.1fs", self.poll_s)
        while not self.stop.is_set():
            try:
                if self.run_one() is None:
                    self.stop.wait(self.poll_s)
            except psycopg.OperationalError as exc:
                log.warning("database unavailable (%s); retrying", exc)
                self.stop.wait(5.0)

    def install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: self.stop.set())


def main(once: bool = False, poll_s: float = 2.0) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    w = Worker(poll_s=poll_s)
    with fgdb.session(w.url) as conn:
        fgdb.migrate(conn)
    if once:
        while w.run_one() is not None:
            pass
        return 0
    w.install_signal_handlers()
    w.loop()
    return 0


def wait_for(conn: psycopg.Connection, campaign_id: int, timeout_s: float = 60.0) -> dict:
    """Poll until a campaign reaches done/failed (tests and scripts)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        c = conn.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,)).fetchone()
        conn.commit()
        if c and c["status"] in ("done", "failed"):
            return c
        time.sleep(0.2)
    raise TimeoutError(f"campaign {campaign_id} did not finish in {timeout_s}s")
