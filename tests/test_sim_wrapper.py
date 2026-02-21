import json

import pytest

from fleetguard.sim import FgsimError

pytestmark = pytest.mark.fgsim


def test_families_and_defaults(fgsim):
    fams = fgsim.families()
    assert "urban_cut_in" in fams and len(fams) == 7
    d = fgsim.defaults()
    assert set(d) == {"name", "perception", "planner", "control"}
    assert d["planner"]["cycle_ms"] == 100.0


def test_scenario_is_deterministic(fgsim):
    a = fgsim.scenario("ped_crossing", 4, geometry=True)
    b = fgsim.scenario("ped_crossing", 4, geometry=True)
    assert a == b
    assert a["id"] == "ped_crossing-4"
    assert len(a["geometry"]["route"]) > 50


def test_run_returns_summary_and_events(fgsim, tmp_path):
    frames = tmp_path / "f.csv"
    r = fgsim.run("highway_follow", 3, frames_path=str(frames))
    assert r["outcome"] in {"completed", "disengaged", "collision", "timeout"}
    assert isinstance(r["events"], list)
    header = frames.read_text().splitlines()[0]
    assert header.startswith("t,x,y,yaw")


def test_compare_two_builds(fgsim):
    out = fgsim.compare("s_curve", 2, {}, {"name": "rc", "planner": {"lateral_bias_m": 0.4}})
    assert out["candidate"]["build"] == "rc"
    assert out["pair"]["lat_mean_abs_diff"] > 0.25


def test_bad_build_key_raises(fgsim):
    with pytest.raises(FgsimError, match="unknown build parameter"):
        fgsim.run("s_curve", 1, build={"planner": {"headway": 1.0}})


def test_batch_streams_progress(fgsim, tmp_path):
    seen = []
    stats = fgsim.batch(count=10, out_dir=tmp_path, baseline={}, candidate={"name": "rc"},
                        families=["s_curve", "urban_cut_in"], chunk=4,
                        on_progress=lambda d, t: seen.append((d, t)))
    assert stats["drives"] == 20
    assert seen == [(4, 10), (8, 10), (10, 10)]
    lines = (tmp_path / "drives.jsonl").read_text().splitlines()
    assert len(lines) == 20
    assert {json.loads(x)["role"] for x in lines} == {"baseline", "candidate"}
