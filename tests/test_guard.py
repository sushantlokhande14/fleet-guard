from fleetguard.diagnostics.context import FailureContext
from fleetguard.diagnostics.guard import check, grounded_numbers


def ctx(**over) -> FailureContext:
    base = dict(
        failure_id=1, campaign_id=2, campaign_name="c", baseline="v2.3", candidate="v2.4-rc1",
        scenario={"id": "s_curve-4", "family": "s_curve", "seed": 4, "weather": "clear", "route_length_m": 512.3},
        category="control_instability", secondary=[], severity=2, score=0.5, first_t=15.7,
        signature="control_instability/s_curve/steer",
        evidence={"steer_reversals_per_s": [0.169, 0.305], "oscillation_events": 3},
        signals={}, metrics=[{"key": "jerk_rms", "name": "jerk", "unit": "", "baseline": 1.5, "candidate": 1.53}],
        pair={}, timeline=[], cluster={"size": 6},
        build_diff=[{"key": "control.actuator_delay_ms", "baseline": 40.0, "candidate": 95.0},
                    {"key": "control.steer_gain", "baseline": 1.0, "candidate": 1.25}],
        repro_command="fgsim compare ...", repro_verified=None,
    )
    base.update(over)
    return FailureContext(**base)


GOOD = {
    "summary": "Steering reversals rose from 0.169/s to 0.305/s on s_curve-4 starting at 15.7 s, with 3 new "
               "oscillation episodes.",
    "likely_cause": "The actuator delay went from 40 ms to 95 ms (control.actuator_delay_ms) while "
                    "control.steer_gain rose 25%, so the loop rings.",
    "suspect_parameters": ["control.actuator_delay_ms", "control.steer_gain"],
    "next_steps": ["Revert the delay and re-run the cluster.", "Plot command vs actual steering."],
    "confidence": "high",
}


def test_grounded_narrative_passes():
    r = check(GOOD, ctx())
    assert r.ok, r.issues
    assert r.narrative["suspect_parameters"] == ["control.actuator_delay_ms", "control.steer_gain"]
    assert r.narrative["confidence"] == "high"


def test_derived_numbers_are_grounded():
    nums = grounded_numbers(ctx())
    # difference, ratio and percent change of baseline/candidate pairs
    assert any(abs(n - 0.136) < 1e-9 for n in nums)
    assert any(abs(n - 25.0) < 1e-9 for n in nums)
    assert any(abs(n - 55.0) < 1e-9 for n in nums)


def test_invented_number_is_rejected():
    bad = dict(GOOD, summary="Steering reversals rose to 0.92/s.")
    r = check(bad, ctx())
    assert not r.ok and any("0.92" in i for i in r.issues)


def test_unchanged_parameter_is_rejected():
    bad = dict(GOOD, likely_cause="planner.headway_s was shortened.")
    r = check(bad, ctx())
    assert not r.ok and "planner.headway_s" in r.issues[0]


def test_unknown_suspects_are_dropped_not_fatal():
    r = check(dict(GOOD, suspect_parameters=["control.steer_gain", "perception.range_m"]), ctx())
    assert r.ok
    assert r.narrative["suspect_parameters"] == ["control.steer_gain"]
    assert any("perception.range_m" in i for i in r.issues)


def test_shape_errors():
    assert not check({}, ctx()).ok
    assert not check(dict(GOOD, next_steps="do things"), ctx()).ok
    assert not check(dict(GOOD, summary="x" * 2000), ctx()).ok
    r = check(dict(GOOD, confidence="certain"), ctx())
    assert r.ok and r.narrative["confidence"] is None


def test_small_counts_are_not_policed():
    r = check(dict(GOOD, summary="Two things happened, then 4 more on s_curve-4."), ctx())
    assert r.ok, r.issues


def test_fraction_as_percent_is_grounded():
    # the model wrote route completion 0.417 as 41.7% (seen with qwen2.5:7b)
    c = ctx(evidence={"route_completion": 0.417, "steer_reversals_per_s": [0.169, 0.305]})
    r = check(dict(GOOD, summary="Only 41.7% of the route was completed on s_curve-4."), c)
    assert r.ok, r.issues
