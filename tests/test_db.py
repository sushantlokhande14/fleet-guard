import psycopg
import pytest

from fleetguard import db as fgdb
from fleetguard import repo
from fleetguard.builds import Registry


def test_migrations_apply_once(db_url):
    conn = fgdb.connect(db_url)
    fgdb.reset(conn)
    first = fgdb.migrate(conn)
    assert first and first[0] == "001_init"
    assert fgdb.migrate(conn) == []
    rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tables = {r["tablename"] for r in rows}
    expected = {"builds", "campaigns", "scenarios", "drives", "drive_events", "pairs", "telemetry_frames"}
    assert expected <= tables
    conn.close()


def test_campaign_status_is_constrained(db):
    db.execute("INSERT INTO builds (name, overrides, params) VALUES ('a', '{}', '{}')")
    db.execute(
        "INSERT INTO campaigns (name, baseline, candidate, families, scenario_count) "
        "VALUES ('c', 'a', 'a', ARRAY['s_curve'], 10)"
    )
    row = db.execute("SELECT status, progress FROM campaigns").fetchone()
    assert row == {"status": "queued", "progress": 0.0}
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE campaigns SET status = 'exploded'")


def test_sync_builds(db, fgsim):
    reg = Registry(defaults=fgsim.defaults())
    assert repo.sync_builds(db, reg) == len(reg.names())
    assert repo.sync_builds(db, reg) == len(reg.names())  # idempotent
    rc1 = repo.get_build(db, "drive-2.4.0-rc1")
    assert rc1["parent"] == "drive-2.3.0"
    assert rc1["overrides"]["control"]["steer_gain"] == 1.25
    assert rc1["params"]["planner"]["cycle_ms"] == 100.0
