import psycopg
import pytest

from fleetguard import db as fgdb


def test_migrations_apply_once(db_url):
    conn = fgdb.connect(db_url)
    fgdb.reset(conn)
    first = fgdb.migrate(conn)
    assert first and first[0] == "001_init"
    assert fgdb.migrate(conn) == []
    tables = {r["tablename"] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    assert {"builds", "campaigns", "scenarios", "drives", "drive_events", "pairs", "telemetry_frames"} <= tables
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
