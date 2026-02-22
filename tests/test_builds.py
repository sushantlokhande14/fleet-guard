import json

import pytest

from fleetguard.builds import Build, BuildError, Registry, deep_merge, diff, flatten

DEFAULTS = {
    "name": "default",
    "perception": {"latency_ms": 60.0, "fp_rate": 0.001},
    "planner": {"headway_s": 1.5, "cycle_ms": 100.0},
    "control": {"steer_gain": 1.0},
}


def write(dirpath, doc):
    (dirpath / f"{doc['name']}.json").write_text(json.dumps(doc))


@pytest.fixture
def reg(tmp_path):
    write(tmp_path, {"name": "base"})
    write(tmp_path, {"name": "rc1", "parent": "base",
                     "planner": {"headway_s": 1.2}, "control": {"steer_gain": 1.3}})
    write(tmp_path, {"name": "rc2", "parent": "rc1", "control": {"steer_gain": 1.0}})
    return Registry(tmp_path, defaults=DEFAULTS)


def test_deep_merge_and_flatten():
    m = deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}, "b": 4})
    assert m == {"a": {"x": 1, "y": 3}, "b": 4}
    assert flatten({"planner": {"headway_s": 1.0}, "name": "x"}) == {"planner.headway_s": 1.0}


def test_overrides_follow_parent_chain(reg):
    expected = {"name": "rc2", "planner": {"headway_s": 1.2}, "control": {"steer_gain": 1.0}}
    assert reg.overrides("rc2") == expected
    assert reg.overrides("base") == {"name": "base"}


def test_effective_fills_defaults(reg):
    eff = reg.effective("rc1")
    assert eff["name"] == "rc1"
    assert eff["planner"] == {"headway_s": 1.2, "cycle_ms": 100.0}
    assert eff["perception"]["latency_ms"] == 60.0


def test_diff_lists_only_changes(reg):
    changes = reg.diff("base", "rc1")
    assert [c.key for c in changes] == ["control.steer_gain", "planner.headway_s"]
    assert changes[0].baseline == 1.0 and changes[0].candidate == 1.3
    # rc2 reverted the gain, only the headway change remains
    assert [c.key for c in reg.diff("base", "rc2")] == ["planner.headway_s"]
    assert diff(DEFAULTS, DEFAULTS) == []


def test_errors(tmp_path, reg):
    with pytest.raises(BuildError, match="unknown build"):
        reg.get("nope")
    with pytest.raises(BuildError, match="duplicate"):
        reg.add(Build("rc1", "", None, {}))
    write(tmp_path, {"name": "bad", "radar": {}})
    with pytest.raises(BuildError, match="unknown keys"):
        Registry(tmp_path)
    r = Registry(tmp_path / "missing")
    assert r.names() == []
    with pytest.raises(BuildError, match="defaults"):
        Registry(tmp_path / "missing").effective("x")


def test_parent_cycle(tmp_path):
    write(tmp_path, {"name": "a", "parent": "b"})
    write(tmp_path, {"name": "b", "parent": "a"})
    with pytest.raises(BuildError, match="cycle"):
        Registry(tmp_path).overrides("a")


@pytest.mark.fgsim
def test_shipped_builds_are_valid(fgsim):
    reg = Registry(defaults=fgsim.defaults())
    assert {"drive-2.3.0", "drive-2.4.0-rc1", "drive-2.4.0-rc2"} <= set(reg.names())
    for name in reg.names():
        # fgsim rejects unknown keys, so a run proves every override is real
        assert fgsim.run("s_curve", 1, build=reg.overrides(name))["build"] == name
    keys = [c.key for c in reg.diff("drive-2.3.0", "drive-2.4.0-rc2")]
    assert keys == ["control.actuator_delay_ms", "planner.latency_per_object_ms"]
