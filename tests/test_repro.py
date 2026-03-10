import pytest

from fleetguard import campaigns, repo, repro
from fleetguard.builds import Registry
from fleetguard.pipeline import post_process

pytestmark = pytest.mark.fgsim


@pytest.fixture
def failed(db, db_url, fgsim, tmp_path):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    repo.upsert_build(db, "k-peds", {"name": "k-peds", "perception": {"ped_far_miss_add": 0.95,
                                                                    "ped_far_range_m": 20}}, {})
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate="k-peds", scenario_count=60,
                           families=["ped_crossing"])
    db.commit()
    campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path, after_ingest=post_process)
    return db.execute("SELECT id FROM failures WHERE campaign_id = %s ORDER BY score DESC", (cid,)).fetchall()


def test_every_failure_reproduces(db, fgsim, failed):
    assert len(failed) >= 5
    for row in failed[:5]:
        r = repro.verify(db, row["id"], fgsim)
        assert r["reproduced"], r["mismatches"]
        assert "fgsim compare --family ped_crossing" in r["command"]
    db.commit()
    n = db.execute("SELECT count(*) AS n FROM failures WHERE repro_verified").fetchone()["n"]
    assert n == 5


def test_tampered_evidence_is_caught(db, fgsim, failed):
    fid = failed[0]["id"]
    case = repro.load_case(db, fid)
    db.execute("UPDATE drives SET recall = recall - 0.2 WHERE id = %s", (case["candidate_drive"],))
    r = repro.verify(db, fid, fgsim)
    assert not r["reproduced"]
    assert any(m.startswith("candidate.recall") for m in r["mismatches"])


def test_command_round_trips_overrides(db, failed):
    case = repro.load_case(db, failed[0]["id"])
    cmd = repro.command(case)
    assert '"ped_far_miss_add":0.95' in cmd
    assert cmd.count("fgsim compare") == 1
