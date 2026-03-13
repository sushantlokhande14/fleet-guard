import pytest

from fleetguard import benchmark, repo
from fleetguard.builds import Registry


def test_summary_math():
    rows = [
        {"case": "a", "category": "route_deviation", "level": "severe", "detected": True, "top1": True,
         "repro_ok": True, "reproduced": True},
        {"case": "b", "category": "route_deviation", "level": "moderate", "detected": True, "top1": False,
         "repro_ok": True, "reproduced": True},
        {"case": "c", "category": "latency_spike", "level": "moderate", "detected": False, "top1": False,
         "repro_ok": True, "reproduced": False},
        {"case": "d", "category": "clean", "level": "control", "passed": True},
        {"case": "e", "category": "clean", "level": "control", "passed": False},
    ]
    s = benchmark.summarize(rows)
    assert s["reproduced"] == {"n": 3, "hit": 2, "rate": 0.6667}
    assert s["top1"]["hit"] == 1
    assert s["by_category"]["latency_spike"]["hit"] == 0
    assert s["by_level"]["severe"] == {"n": 1, "hit": 1, "rate": 1.0}
    assert s["controls"] == {"n": 2, "false_positives": 1}
    assert s["missed"] == ["c"]


@pytest.mark.fgsim
def test_small_benchmark_run(db, db_url, fgsim, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    db.commit()
    seen = []
    result = benchmark.run(db_url, scenario_count=70, case_filter="route_deviation.lateral_bias.severe",
                           sim=fgsim, threads=4, on_case=seen.append)
    assert len(result["cases"]) == 1 == len(seen)
    row = result["cases"][0]
    assert row["detected"] and row["repro_ok"] and row["reproduced"]
    assert result["drives"] == 140
    benchmark.write(result, tmp_path / "out")
    md = (tmp_path / "out" / "benchmark.md").read_text()
    assert "seeded regressions reproduced | **1 / 1 (100%)**" in md
