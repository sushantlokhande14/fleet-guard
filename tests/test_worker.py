import threading

import pytest

from fleetguard import campaigns, repo, worker
from fleetguard import db as fgdb
from fleetguard.builds import Registry


@pytest.fixture
def queued(db, fgsim):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    ids = [campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc2", scenario_count=14)
           for _ in range(3)]
    db.commit()
    return ids


def test_claims_are_exclusive(db_url, queued):
    a, b = fgdb.connect(db_url), fgdb.connect(db_url)
    try:
        # first claimer holds its row lock (no commit yet) while the second claims
        row_a = a.execute(worker.CLAIM_SQL).fetchone()
        row_b = b.execute(worker.CLAIM_SQL).fetchone()
        assert row_a["id"] != row_b["id"]
        assert row_a["id"] == queued[0]  # oldest first
        a.commit()
        b.commit()
    finally:
        a.close()
        b.close()


@pytest.mark.fgsim
def test_worker_drains_the_queue(db, db_url, fgsim, queued, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    w = worker.Worker(url=db_url, sim=fgsim, poll_s=0.05)
    done = [w.run_one() for _ in range(4)]
    assert done == [*queued, None]
    rows = db.execute("SELECT status, verdict FROM campaigns ORDER BY id").fetchall()
    assert all(r["status"] == "done" and r["verdict"] is not None for r in rows)


@pytest.mark.fgsim
def test_loop_stops_cleanly(db_url, fgsim, queued, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    w = worker.Worker(url=db_url, sim=fgsim, poll_s=0.05)
    t = threading.Thread(target=w.loop)
    t.start()
    conn = fgdb.connect(db_url)
    try:
        assert worker.wait_for(conn, queued[-1], timeout_s=60)["status"] == "done"
    finally:
        w.stop.set()
        t.join(timeout=10)
        conn.close()
    assert not t.is_alive()


def test_failed_campaign_does_not_kill_the_worker(db, db_url, fgsim, queued, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    db.execute("UPDATE builds SET overrides = '{\"planner\": {\"nope\": 1}}' WHERE name = 'drive-2.4.0-rc2'")
    db.commit()
    w = worker.Worker(url=db_url, sim=fgsim)
    assert w.run_one() == queued[0]
    c = db.execute("SELECT status, error FROM campaigns WHERE id = %s", (queued[0],)).fetchone()
    assert c["status"] == "failed" and "nope" in c["error"]
