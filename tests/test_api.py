import pytest
from fastapi.testclient import TestClient

from fleetguard import repo
from fleetguard.api import create_app
from fleetguard.builds import Registry
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
