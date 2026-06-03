import httpx
import pytest
from fastapi.testclient import TestClient

from fleetguard import repo
from fleetguard.api import create_app
from fleetguard.builds import Registry
from fleetguard.diagnostics.llm import LLMClient
from fleetguard.worker import Worker

pytestmark = pytest.mark.fgsim


@pytest.fixture
def client(db, db_url, fgsim):
    repo.sync_builds(db, Registry(defaults=fgsim.defaults()))
    db.commit()
    with TestClient(create_app(db_url, sim=fgsim)) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["fgsim"]


def test_families(client):
    assert "construction_shift" in client.get("/api/families").json()


def test_builds(client):
    names = [b["name"] for b in client.get("/api/builds").json()]
    assert names[:3] == ["drive-2.3.0", "drive-2.4.0-rc1", "drive-2.4.0-rc2"]
    rc1 = client.get("/api/builds/drive-2.4.0-rc1").json()
    assert rc1["params"]["control"]["steer_gain"] == 1.25
    assert client.get("/api/builds/nope").status_code == 404


def test_seeded_builds_hidden_by_default(client, db):
    repo.upsert_build(db, "seeded/x", {"name": "seeded/x"}, {})
    db.commit()
    assert "seeded/x" not in [b["name"] for b in client.get("/api/builds").json()]
    assert "seeded/x" in [b["name"] for b in client.get("/api/builds?include_seeded=true").json()]
    assert client.get("/api/builds/seeded/x").json()["name"] == "seeded/x"


def test_build_diff(client):
    d = client.get("/api/builds/drive-2.3.0/diff/drive-2.4.0-rc2").json()
    assert [c["key"] for c in d] == ["control.actuator_delay_ms", "planner.latency_per_object_ms"]
    assert d[0] == {"key": "control.actuator_delay_ms", "baseline": 40.0, "candidate": 95}


def test_create_and_poll_campaign(client, db_url, fgsim, tmp_path, monkeypatch):
    r = client.post("/api/campaigns", json={"baseline": "drive-2.3.0", "candidate": "drive-2.4.0-rc1",
                                            "scenario_count": 70})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["status"] == "queued"
    assert [c["id"] for c in client.get("/api/campaigns?status=queued").json()] == [cid]

    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    Worker(url=db_url, sim=fgsim).run_one()
    c = client.get(f"/api/campaigns/{cid}").json()
    assert c["status"] == "done"
    assert c["verdict"]["status"] == "regression"
    listed = client.get("/api/campaigns").json()[0]
    assert listed["verdict"] == "regression" and listed["failures"] == c["verdict"]["failures"]

    m = client.get(f"/api/campaigns/{cid}/metrics").json()
    assert [r["role"] for r in m["roles"]] == ["baseline", "candidate"]
    assert len({f["family"] for f in m["families"]}) == 7


def test_create_validation(client):
    bad_build = client.post("/api/campaigns", json={"baseline": "drive-2.3.0", "candidate": "nope"})
    assert bad_build.status_code == 422 and "unknown build" in bad_build.json()["detail"]
    bad_family = client.post("/api/campaigns", json={"baseline": "drive-2.3.0", "candidate": "drive-2.3.0",
                                                     "families": ["moon"]})
    assert bad_family.status_code == 422
    too_many = client.post("/api/campaigns", json={"baseline": "drive-2.3.0", "candidate": "drive-2.3.0",
                                                   "scenario_count": 10**7})
    assert too_many.status_code == 422
    assert client.get("/api/campaigns/999").status_code == 404


@pytest.fixture
def finished(client, db_url, fgsim, tmp_path, monkeypatch):
    monkeypatch.setenv("FG_RUNS_DIR", str(tmp_path))
    # report endpoints are tested from a clean slate; auto-reports have their own tests in test_pipeline
    monkeypatch.setenv("FG_AUTO_REPORTS", "0")
    cid = client.post("/api/campaigns", json={"baseline": "drive-2.3.0", "candidate": "drive-2.4.0-rc1",
                                              "scenario_count": 140}).json()["id"]
    Worker(url=db_url, sim=fgsim).run_one()
    return cid


def test_failures_list_and_filters(client, finished):
    all_ = client.get(f"/api/campaigns/{finished}/failures").json()
    assert all_["total"] == len(all_["items"]) > 0
    control = client.get(f"/api/campaigns/{finished}/failures?category=control_instability").json()
    assert 0 < control["total"] <= all_["total"]
    assert {i["category"] for i in control["items"]} == {"control_instability"}
    s_curve = client.get(f"/api/campaigns/{finished}/failures?family=s_curve&limit=2").json()
    assert len(s_curve["items"]) <= 2 and s_curve["total"] >= len(s_curve["items"])
    sev = [i["severity"] for i in all_["items"]]
    assert sev == sorted(sev, reverse=True)


def test_clusters(client, finished):
    cl = client.get(f"/api/campaigns/{finished}/clusters").json()
    assert cl[0]["failures"] >= cl[-1]["failures"]
    total = client.get(f"/api/campaigns/{finished}/failures").json()["total"]
    assert sum(c["failures"] for c in cl) == total
    ex = client.get(f"/api/failures/{cl[0]['example_id']}").json()
    assert ex["failure"]["signature"] == cl[0]["signature"]


def test_failure_detail(client, finished):
    fid = client.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
    d = client.get(f"/api/failures/{fid}").json()
    assert d["campaign"]["candidate"] == "drive-2.4.0-rc1"
    assert d["baseline"]["role"] == "baseline" and d["candidate"]["role"] == "candidate"
    assert isinstance(d["candidate"]["events"], list)
    assert {c["key"] for c in d["build_diff"]} >= {"control.steer_gain", "control.actuator_delay_ms"}
    assert d["repro_command"].startswith("echo ")
    assert client.get("/api/failures/0").status_code == 404


def test_telemetry_stored_and_replayed_match(client, db, finished):
    fid = client.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
    stored = client.get(f"/api/failures/{fid}/telemetry").json()
    assert stored["source"] == "stored"
    assert len(stored["baseline"]["t"]) > 50 and stored["candidate"]["t"][0] == 0.0
    # drop the stored frames: the endpoint regenerates them, bit for bit (up to float4 storage)
    db.execute("DELETE FROM telemetry_frames")
    db.commit()
    replayed = client.get(f"/api/failures/{fid}/telemetry").json()
    assert replayed["source"] == "replayed"
    for role in ("baseline", "candidate"):
        assert len(replayed[role]["t"]) == len(stored[role]["t"])
        assert replayed[role]["x"][-1] == pytest.approx(stored[role]["x"][-1], abs=1e-3)


def test_scenario_geometry(client, finished):
    fid = client.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
    sc = client.get(f"/api/failures/{fid}/scenario").json()
    assert len(sc["geometry"]["route"]) > 20 and "actors" in sc


def test_repro_endpoint(client, finished):
    fid = client.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
    r = client.post(f"/api/failures/{fid}/repro").json()
    assert r["reproduced"] is True and r["mismatches"] == []
    assert client.get(f"/api/failures/{fid}").json()["failure"]["repro_verified"] is True


def test_metrics_endpoint(client):
    client.get("/api/health")
    text = client.get("/metrics").text
    assert "fleetguard_db_up 1.0" in text
    assert 'fleetguard_api_requests_total{method="GET",route="/api/health",status="200"}' in text


def test_reports_api(client, finished):
    fid = client.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
    assert client.get(f"/api/failures/{fid}/report").status_code == 404
    r = client.post(f"/api/failures/{fid}/report?llm=false")
    assert r.status_code == 201 and r.json()["generator"] == "template"
    assert client.get(f"/api/failures/{fid}/report").json()["id"] == r.json()["id"]
    assert len(client.get(f"/api/failures/{fid}/reports").json()) == 1


def test_report_api_uses_llm_factory(db, db_url, fgsim, finished):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, text="model loading")

    app = create_app(db_url, sim=fgsim,
                     llm_factory=lambda: LLMClient(base_url="http://fake/v1", transport=httpx.MockTransport(handler)))
    with TestClient(app) as c:
        fid = c.get(f"/api/campaigns/{finished}/failures?limit=1").json()["items"][0]["id"]
        r = c.post(f"/api/failures/{fid}/report").json()
    assert len(calls) == 1
    assert r["generator"] == "template" and "503" in r["meta"]["llm_error"]


def test_summary_markdown(client, finished):
    r = client.get(f"/api/campaigns/{finished}/summary.md?ui=http://ui")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert "**REGRESSION**" in r.text and f"[#{finished}](http://ui/campaigns/{finished})" in r.text
    assert client.get("/api/campaigns/999/summary.md").status_code == 404
