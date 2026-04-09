import pytest
from fastapi.testclient import TestClient

from fleetguard.api import create_app


@pytest.fixture
def client(db, db_url, fgsim):
    db.execute("INSERT INTO builds (name, overrides, params) VALUES ('a', '{}', '{}')")
    db.execute("INSERT INTO campaigns (id, name, baseline, candidate, families, scenario_count)"
               " VALUES (7, 'c', 'a', 'a', ARRAY['s_curve'], 1)")
    db.commit()
    with TestClient(create_app(db_url, sim=fgsim)) as c:
        yield c


def payload(status, fingerprint="abc", campaign="7", ends="0001-01-01T00:00:00Z"):
    return {
        "version": "4", "status": status, "receiver": "triage", "groupLabels": {}, "commonLabels": {},
        "alerts": [{
            "status": status, "fingerprint": fingerprint, "startsAt": "2026-04-09T17:00:00Z", "endsAt": ends,
            "labels": {"alertname": "CandidateRegression", "severity": "warning", "campaign": campaign,
                       "candidate": "rc1", "baseline": "v2"},
            "annotations": {"summary": "rc1 regressed against v2"},
        }],
    }


def test_firing_then_resolved(client):
    assert client.post("/api/alerts/webhook", json=payload("firing")).json() == {"received": 1}
    firing = client.get("/api/alerts").json()
    assert len(firing) == 1
    a = firing[0]
    assert (a["alertname"], a["campaign_id"], a["severity"], a["ends_at"]) == ("CandidateRegression", 7, "warning",
                                                                                None)
    client.post("/api/alerts/webhook", json=payload("resolved", ends="2026-04-09T18:00:00Z"))
    assert client.get("/api/alerts").json() == []
    resolved = client.get("/api/alerts?status=resolved").json()
    assert resolved[0]["ends_at"].startswith("2026-04-09T18:00:00")


def test_unknown_campaign_is_not_linked(client):
    client.post("/api/alerts/webhook", json=payload("firing", fingerprint="x", campaign="999"))
    client.post("/api/alerts/webhook", json=payload("firing", fingerprint="y", campaign=""))
    assert {a["campaign_id"] for a in client.get("/api/alerts").json()} == {None}


def test_rejects_garbage(client):
    assert client.post("/api/alerts/webhook", json={"hello": "world"}).status_code == 422
