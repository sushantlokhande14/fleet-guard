import collections

import pytest

from fleetguard import campaigns, classifiers, repo
from fleetguard.builds import Registry
from fleetguard.classifiers import Failure, Signal, attribute, signature


def sig(cat, t, score=0.8, **ev):
    return Signal("s-1", cat, score, t, ev)


# --- attribution ------------------------------------------------------------------

def test_precursor_explains_the_disengagement():
    f = attribute([sig("disengagement", 12.0, 0.9, reason="ttc_takeover"),
                   sig("perception_error", 9.5), sig("control_instability", 11.0)])
    assert f.category == "perception_error"
    assert f.severity == 3
    assert f.secondary == ["control_instability", "disengagement"]
    assert set(f.signals) == {"disengagement", "perception_error", "control_instability"}


def test_late_signal_is_not_a_cause():
    f = attribute([sig("disengagement", 5.0, reason="ttc_takeover"), sig("route_deviation", 9.0)])
    assert f.category == "disengagement"


def test_no_precursor_means_planning():
    f = attribute([sig("disengagement", 7.0, reason="ttc_takeover")])
    assert (f.category, f.severity, f.secondary) == ("disengagement", 3, [])


def test_untimed_cause_needs_strength():
    weak = attribute([sig("disengagement", 7.0), sig("perception_error", None, 0.2)])
    assert weak.category == "disengagement"
    strong = attribute([sig("disengagement", 7.0), sig("perception_error", None, 0.9)])
    assert strong.category == "perception_error"


def test_without_disengagement_earliest_timed_wins():
    f = attribute([sig("route_deviation", 6.0), sig("control_instability", 4.0),
                   sig("latency_spike", None, 1.0)])
    assert f.category == "control_instability"
    assert f.severity == 2
    only_metrics = attribute([sig("latency_spike", None, 0.4), sig("route_deviation", None, 0.6)])
    assert only_metrics.category == "route_deviation" and only_metrics.severity == 1


def test_ties_go_upstream():
    f = attribute([sig("route_deviation", 5.0), sig("perception_error", 5.0)])
    assert f.category == "perception_error"


def test_signatures():
    def fail(cat, **ev):
        return Failure("s", cat, 2, 0.5, 1.0, ev)

    assert signature(fail("disengagement", reason="ttc_takeover", detail="ttc_takeover pedestrian 1"),
                     "ped_crossing") == "disengagement/ped_crossing/ttc_takeover:pedestrian"
    assert signature(fail("disengagement", reason="", outcome="timeout"), "x") == "disengagement/x/timeout"
    assert signature(fail("perception_error", new_misses=[{"object": "pedestrian 2"}], new_phantoms=0),
                     "ped_crossing") == "perception_error/ped_crossing/pedestrian"
    assert signature(fail("perception_error", new_misses=[], new_phantoms=3), "f").endswith("/phantom")
    assert signature(fail("latency_spike", watchdog=True, deadline_misses=[0, 5]), "f").endswith("/watchdog")
    assert signature(fail("latency_spike", watchdog=False, deadline_misses=[1, 1]), "f").endswith("/p99")
    assert signature(fail("route_deviation", lane_departure=True), "f").endswith("/lane_departure")
    assert signature(fail("control_instability", axes=["steer_oscillation", "accel_oscillation"]),
                     "f").endswith("/accel+steer")


# --- end to end against the simulator ----------------------------------------------

KNOBS = {
    "clean": {},
    "bias": {"planner": {"lateral_bias_m": 0.5}},
    "spikes": {"planner": {"spike_prob": 0.05}},
    "peds": {"perception": {"ped_far_miss_add": 0.95, "ped_far_range_m": 20}},
    "steer": {"control": {"steer_gain": 1.7, "actuator_delay_ms": 120}},
}


@pytest.fixture
def classified(db, db_url, fgsim, tmp_path):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    out = {}
    for name, knob in KNOBS.items():
        repo.upsert_build(db, f"k-{name}", {"name": f"k-{name}", **knob}, {})
        cid = campaigns.create(db, baseline="drive-2.3.0", candidate=f"k-{name}", scenario_count=70)
        db.commit()
        campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path)
        out[name] = classifiers.classify_campaign(db, cid)
        db.commit()
    return out


@pytest.mark.fgsim
def test_knobs_land_in_their_category(classified):
    assert classified["clean"] == []
    top = {name: collections.Counter(f.category for f in fails).most_common(1)[0][0]
           for name, fails in classified.items() if fails}
    assert top == {"bias": "route_deviation", "spikes": "latency_spike", "peds": "perception_error",
                   "steer": "control_instability"}


@pytest.mark.fgsim
def test_failures_are_stored_once_per_scenario(db, classified):
    rows = db.execute("SELECT campaign_id, scenario_id, count(*) AS n FROM failures "
                      "GROUP BY 1, 2 HAVING count(*) > 1").fetchall()
    assert rows == []
    r = db.execute("SELECT * FROM failures WHERE category = 'perception_error' LIMIT 1").fetchone()
    assert r["classifier_version"] == classifiers.CLASSIFIER_VERSION
    assert r["signature"].startswith("perception_error/")
    assert "recall" in r["evidence"]
