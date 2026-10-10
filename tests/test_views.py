import pytest

from fleetguard import campaigns, repo
from fleetguard.builds import Registry

pytestmark = pytest.mark.fgsim


@pytest.fixture
def ran(db, db_url, fgsim, tmp_path):
    """A small campaign of a build against itself plus one against a steering regression."""
    reg = Registry(defaults=fgsim.defaults())
    repo.sync_builds(db, reg)
    wobbly = {"name": "wobbly", "control": {"steer_gain": 1.9, "actuator_delay_ms": 130}}
    repo.upsert_build(db, "wobbly", wobbly, {})
    same = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.3.0", scenario_count=28)
    bad = campaigns.create(db, baseline="drive-2.3.0", candidate="wobbly", scenario_count=28)
    db.commit()
    for cid in (same, bad):
        campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path)
    return same, bad


def test_role_metrics(db, ran):
    same, bad = ran
    rows = {r["role"]: r for r in db.execute(
        "SELECT * FROM campaign_role_metrics WHERE campaign_id = %s", (same,))}
    assert rows["baseline"]["drives"] == rows["candidate"]["drives"] == 28
    # a build against itself is identical on every KPI
    for k in ("completed", "km", "recall", "planner_p99_median_ms", "steer_reversal_rate"):
        assert rows["baseline"][k] == pytest.approx(rows["candidate"][k]), k
    rows = {r["role"]: r for r in db.execute(
        "SELECT * FROM campaign_role_metrics WHERE campaign_id = %s", (bad,))}
    assert rows["candidate"]["steer_reversal_rate"] > 2 * rows["baseline"]["steer_reversal_rate"]


def test_family_metrics_cover_all_families(db, ran):
    _, bad = ran
    fams = {r["family"] for r in db.execute(
        "SELECT family FROM campaign_family_metrics WHERE campaign_id = %s", (bad,))}
    assert len(fams) == 7


def test_new_candidate_events_empty_for_identical_builds(db, ran):
    same, bad = ran
    n = db.execute("SELECT count(*) AS n FROM new_candidate_events WHERE campaign_id = %s",
                   (same,)).fetchone()["n"]
    assert n == 0
    kinds = {r["kind"] for r in db.execute(
        "SELECT DISTINCT kind FROM new_candidate_events WHERE campaign_id = %s", (bad,))}
    assert "steer_oscillation" in kinds


def test_pair_detail(db, ran):
    _, bad = ran
    r = db.execute("SELECT * FROM pair_detail WHERE campaign_id = %s LIMIT 1", (bad,)).fetchone()
    assert r["family"] and r["base_outcome"] and r["cand_outcome"]
