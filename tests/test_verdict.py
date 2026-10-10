import pytest

from fleetguard import campaigns, repo, verdict
from fleetguard.builds import Registry
from fleetguard.pipeline import post_process

pytestmark = pytest.mark.fgsim


@pytest.fixture
def setup(db, fgsim):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    db.commit()


def run(db, db_url, fgsim, tmp_path, candidate, count=140):
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate=candidate, scenario_count=count)
    db.commit()
    campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path, after_ingest=post_process)
    return campaigns.get(db, cid)


def test_identical_build_passes(db, db_url, fgsim, tmp_path, setup):
    c = run(db, db_url, fgsim, tmp_path, "drive-2.3.0")
    v = c["verdict"]
    assert v["status"] == "pass"
    assert v["failures"] == 0 and v["flagged"] == [] and v["top_category"] is None
    assert set(v["categories"]) == {"disengagement", "latency_spike", "route_deviation", "perception_error",
                                    "control_instability"}


def test_rc1_regresses_in_control_and_latency(db, db_url, fgsim, tmp_path, setup):
    # rc1 ships a steering retune with more actuator delay and a slower fusion step
    c = run(db, db_url, fgsim, tmp_path, "drive-2.4.0-rc1")
    v = c["verdict"]
    assert v["status"] == "regression"
    assert set(v["flagged"]) == {"control_instability", "latency_spike"}
    assert v["top_clusters"][0]["n"] >= v["top_clusters"][-1]["n"]


def test_thresholds(db, setup):
    db.execute("INSERT INTO campaigns (id, name, baseline, candidate, families, scenario_count)"
               " VALUES (99, 'x', 'drive-2.3.0', 'drive-2.3.0', ARRAY['s_curve'], 1000)")
    db.execute("INSERT INTO scenarios (id, family, seed, weather, route_length_m, speed_limit_mps, params)"
               " SELECT 's_curve-' || g, 's_curve', g, 'clear', 500, 15, '{}' FROM generate_series(1, 10) g")
    for i in range(1, 5):
        db.execute("INSERT INTO failures (campaign_id, scenario_id, category, severity, score, signature,"
                   " evidence, signals, classifier_version) VALUES (99, %s, 'route_deviation', 2, 0.5,"
                   " 'route_deviation/s_curve/offset', '{}', '{}', 't')", (f"s_curve-{i}",))
    v = verdict.compute(db, 99)
    # 4 failures in 1000 scenarios is under 5 per 1000: noise, not a regression
    expected = {"failures": 4, "critical": 0, "per_1000": 4.0, "flagged": False}
    assert v["categories"]["route_deviation"] == expected
    assert v["status"] == "pass"
    db.execute("UPDATE campaigns SET scenario_count = 500 WHERE id = 99")
    assert verdict.compute(db, 99)["flagged"] == ["route_deviation"]
