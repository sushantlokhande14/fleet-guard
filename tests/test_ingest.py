import json

import pytest

from fleetguard.ingest import ingest_batch

pytestmark = pytest.mark.fgsim


@pytest.fixture
def campaign(db):
    db.execute("INSERT INTO builds (name, overrides, params) VALUES ('base', '{}', '{}'), ('rc', '{}', '{}')")
    row = db.execute(
        "INSERT INTO campaigns (name, baseline, candidate, families, scenario_count)"
        " VALUES ('t', 'base', 'rc', ARRAY['urban_cut_in','s_curve'], 12) RETURNING id"
    ).fetchone()
    db.commit()
    return row["id"]


def run_batch(fgsim, tmp_path, candidate):
    return fgsim.batch(count=12, out_dir=tmp_path, baseline={"name": "base"}, candidate=candidate,
                       families=["urban_cut_in", "s_curve"], frames="all", max_frame_pairs=4)


def test_ingest_counts_match_files(db, fgsim, tmp_path, campaign):
    stats = run_batch(fgsim, tmp_path, {"name": "rc", "control": {"steer_gain": 1.7}})
    counts = ingest_batch(db, campaign, tmp_path)
    assert counts["drives"] == stats["drives"] == 24
    assert counts["events"] == stats["events"]
    assert counts["pairs"] == 12
    frame_lines = len((tmp_path / "frames.csv").read_text().splitlines()) - 1
    assert counts["frames"] == frame_lines > 0

    n = db.execute("SELECT count(*) AS n FROM drives WHERE campaign_id = %s", (campaign,)).fetchone()["n"]
    assert n == 24
    assert db.execute("SELECT count(*) AS n FROM scenarios").fetchone()["n"] == 12


def test_pairs_point_at_the_right_drives(db, fgsim, tmp_path, campaign):
    run_batch(fgsim, tmp_path, {"name": "rc"})
    ingest_batch(db, campaign, tmp_path)
    rows = db.execute(
        """
        SELECT p.scenario_id, b.role AS brole, b.build AS bbuild, c.role AS crole, c.build AS cbuild
          FROM pairs p JOIN drives b ON b.id = p.baseline_drive JOIN drives c ON c.id = p.candidate_drive
        """
    ).fetchall()
    assert len(rows) == 12
    for r in rows:
        assert (r["brole"], r["bbuild"], r["crole"], r["cbuild"]) == ("baseline", "base", "candidate", "rc")


def test_nulls_and_infinities_survive(db, fgsim, tmp_path, campaign):
    run_batch(fgsim, tmp_path, {"name": "rc"})
    ingest_batch(db, campaign, tmp_path)
    # s_curve drives without a lead have no TTC: JSON null -> SQL NULL
    drives = [json.loads(x) for x in (tmp_path / "drives.jsonl").read_text().splitlines()]
    no_ttc = sum(1 for d in drives if d["min_ttc"] is None)
    got = db.execute("SELECT count(*) AS n FROM drives WHERE min_ttc IS NULL").fetchone()["n"]
    assert got == no_ttc
    # empty CSV cells (no lead) are NULL, not zero
    assert db.execute("SELECT count(*) AS n FROM telemetry_frames WHERE lead_gap = 0").fetchone()["n"] == 0


def test_scenarios_are_shared_between_campaigns(db, fgsim, tmp_path, campaign):
    run_batch(fgsim, tmp_path, {"name": "rc"})
    ingest_batch(db, campaign, tmp_path)
    second = db.execute(
        "INSERT INTO campaigns (name, baseline, candidate, families, scenario_count)"
        " VALUES ('t2', 'base', 'rc', ARRAY['s_curve'], 12) RETURNING id"
    ).fetchone()["id"]
    ingest_batch(db, second, tmp_path)
    assert db.execute("SELECT count(*) AS n FROM scenarios").fetchone()["n"] == 12
    assert db.execute("SELECT count(*) AS n FROM drives").fetchone()["n"] == 48
