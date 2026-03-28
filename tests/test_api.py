import pytest
from fastapi.testclient import TestClient

from fleetguard import repo
from fleetguard.api import create_app
from fleetguard.builds import Registry

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
