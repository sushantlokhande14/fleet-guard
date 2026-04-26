import pytest

from fleetguard import campaigns, repo
from fleetguard.builds import Registry
from fleetguard.pipeline import auto_reports, post_process

pytestmark = pytest.mark.fgsim


def run(db, db_url, fgsim, tmp_path, candidate, count=140):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate=candidate, scenario_count=count)
    db.commit()
    campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path, after_ingest=post_process)
    return cid


def test_one_report_per_top_cluster(db, db_url, fgsim, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_AUTO_REPORTS", "3")
    cid = run(db, db_url, fgsim, tmp_path, "drive-2.4.0-rc1")
    clusters = db.execute("SELECT signature, count(*) AS n FROM failures WHERE campaign_id = %s"
                          " GROUP BY signature ORDER BY n DESC, signature", (cid,)).fetchall()
    reported = db.execute(
        "SELECT f.signature FROM reports r JOIN failures f ON f.id = r.failure_id WHERE f.campaign_id = %s",
        (cid,)).fetchall()
    assert len(reported) == min(3, len(clusters))
    assert {r["signature"] for r in reported} == {c["signature"] for c in clusters[:3]}
    assert {r["generator"] for r in db.execute("SELECT generator FROM reports")} == {"template"}


def test_clean_campaign_and_disabled(db, db_url, fgsim, tmp_path, monkeypatch):
    cid = run(db, db_url, fgsim, tmp_path, "drive-2.3.0", count=70)
    assert db.execute("SELECT count(*) AS n FROM reports").fetchone()["n"] == 0
    assert auto_reports(db, cid, max_clusters=0) == []
