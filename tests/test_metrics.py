import pytest
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from fleetguard import campaigns, metrics, repo
from fleetguard.builds import Registry
from fleetguard.pipeline import post_process


def scrape(url) -> str:
    return generate_latest(metrics.fleet_registry(url)).decode()


def samples(text: str, name: str) -> list[tuple[dict, float]]:
    return [(s.labels, s.value) for fam in text_string_to_metric_families(text) for s in fam.samples
            if s.name == name]


def test_db_down_is_reported_not_raised():
    text = scrape("postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=1")
    assert "fleetguard_db_up 0.0" in text


def test_empty_database(db, db_url):
    text = scrape(db_url)
    assert "fleetguard_db_up 1.0" in text
    assert ({"status": "queued"}, 0.0) in samples(text, "fleetguard_campaigns")


@pytest.mark.fgsim
def test_latest_campaign_kpis(db, db_url, fgsim, tmp_path):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    cid = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc1", scenario_count=140)
    benchmark_cid = campaigns.create(db, baseline="drive-2.3.0", candidate="drive-2.4.0-rc2", scenario_count=7,
                                     tags={"benchmark": "x"})
    db.commit()
    campaigns.run(cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path, after_ingest=post_process)
    campaigns.run(benchmark_cid, url=db_url, sim=fgsim, threads=4, runs_dir=tmp_path, after_ingest=post_process)
    text = scrape(db_url)
    reg = samples(text, "fleetguard_campaign_regression")
    assert reg == [({"campaign": str(cid), "candidate": "drive-2.4.0-rc1", "baseline": "drive-2.3.0"}, 1.0)]
    fails = {lb["category"]: v for lb, v in samples(text, "fleetguard_campaign_failures")}
    assert fails["control_instability"] > 0 and len(fails) == 5
    roles = {lb["role"] for lb, _ in samples(text, "fleetguard_build_planner_p99_ms")}
    assert roles == {"baseline", "candidate"}
    # benchmark campaigns stay out of the build-level series
    assert "drive-2.4.0-rc2" not in text
    assert ({"status": "done"}, 2.0) in samples(text, "fleetguard_campaigns")


def test_worker_registry_names():
    names = {m.name for m in metrics.WORKER_REGISTRY.collect()}
    assert {"fleetguard_worker_campaigns", "fleetguard_worker_drives_simulated", "fleetguard_worker_busy"} <= names
