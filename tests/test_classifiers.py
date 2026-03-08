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

