import pytest

from fleetguard import campaigns, repo
from fleetguard.builds import Registry

pytestmark = pytest.mark.fgsim


@pytest.fixture
def builds(db, fgsim):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    db.commit()


def test_create_validates_builds(db, builds):
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc1", scenario_count=14)
    c = campaigns.get(db, cid)
    assert c["status"] == "queued"
    assert c["name"] == "drive-2.4.0-rc1 vs drive-2.3.0"
    assert len(c["families"]) == 7
    with pytest.raises(campaigns.CampaignError, match="unknown build"):
        campaigns.create(db, baseline="drive-2.3.0", candidate="nope", scenario_count=1)


def test_run_end_to_end(db, db_url, builds, fgsim, tmp_path):
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc1", scenario_count=21,
                           families=["construction_shift", "s_curve", "urban_cut_in"])
    db.commit()
    seen = []

    def post(conn, campaign_id):
        seen.append(conn.execute("SELECT status FROM campaigns WHERE id = %s", (campaign_id,)).fetchone())

    out = campaigns.run(cid, url=db_url, sim=fgsim, threads=2, runs_dir=tmp_path, after_ingest=post)
    assert out["ingested"]["drives"] == 42
    c = campaigns.get(db, cid)
    assert c["status"] == "done" and c["progress"] == 1.0
    assert c["started_at"] is not None and c["finished_at"] >= c["started_at"]
    assert c["drives_per_second"] > 0
    assert seen == [{"status": "classifying"}]
    assert not (tmp_path / f"campaign-{cid}").exists()  # working files cleaned up


def test_failure_is_recorded(db, db_url, builds, fgsim, tmp_path):
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc1", scenario_count=7)
    db.execute("UPDATE builds SET overrides = '{\"planner\": {\"bogus\": 1}}' WHERE name = 'drive-2.4.0-rc1'")
    db.commit()
    with pytest.raises(Exception, match="unknown build parameter"):
        campaigns.run(cid, url=db_url, sim=fgsim, runs_dir=tmp_path)
    c = campaigns.get(db, cid)
    assert c["status"] == "failed"
    assert "unknown build parameter" in c["error"]
