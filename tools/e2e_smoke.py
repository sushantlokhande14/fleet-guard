"""End-to-end smoke test against a running stack (docker compose up -d).

Only talks HTTP, like a user or a CI pipeline would:

    python tools/e2e_smoke.py [--api http://localhost:8000] [--web http://localhost:8080]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: dict | None = None, raw: bool = False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = r.read().decode()
        return payload if raw else json.loads(payload)

    def get(self, path: str, **kw):
        return self.call("GET", path, **kw)

    def post(self, path: str, body: dict | None = None):
        return self.call("POST", path, body)


def step(name: str):
    def deco(fn):
        def run(*args, **kw):
            t0 = time.monotonic()
            out = fn(*args, **kw)
            print(f"  ok  {name} ({time.monotonic() - t0:.1f}s)")
            return out
        return run
    return deco


def wait_done(api: Client, cid: int, timeout_s: float = 300) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        c = api.get(f"/api/campaigns/{cid}")
        if c["status"] in ("done", "failed"):
            return c
        time.sleep(1)
    raise TimeoutError(f"campaign {cid} still {c['status']} after {timeout_s}s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", default="http://localhost:8080")
    ap.add_argument("--scenarios", type=int, default=140)
    args = ap.parse_args()
    api, web = Client(args.api), Client(args.web)

    @step("api healthy")
    def health():
        assert api.get("/api/health")["status"] == "ok"

    @step("regressed candidate is flagged")
    def regression():
        c = api.post("/api/campaigns", {"baseline": "drive-2.3.0", "candidate": "drive-2.4.0-rc1",
                                        "scenario_count": args.scenarios})
        c = wait_done(api, c["id"])
        assert c["status"] == "done", c["error"]
        v = c["verdict"]
        assert v["status"] == "regression", v
        assert "control_instability" in v["flagged"], v["flagged"]
        return c["id"]

    @step("identical build passes")
    def clean():
        c = api.post("/api/campaigns", {"baseline": "drive-2.3.0", "candidate": "drive-2.3.0",
                                        "scenario_count": args.scenarios})
        c = wait_done(api, c["id"])
        assert c["verdict"]["status"] == "pass" and c["verdict"]["failures"] == 0, c["verdict"]

    @step("clusters, detail, telemetry and scenario")
    def triage(cid: int) -> int:
        clusters = api.get(f"/api/campaigns/{cid}/clusters")
        assert clusters and clusters[0]["failures"] >= clusters[-1]["failures"]
        fid = clusters[0]["example_id"]
        d = api.get(f"/api/failures/{fid}")
        assert d["failure"]["signature"] == clusters[0]["signature"]
        assert any(c["key"] == "control.actuator_delay_ms" for c in d["build_diff"])
        tel = api.get(f"/api/failures/{fid}/telemetry")
        assert len(tel["candidate"]["t"]) > 50
        assert api.get(f"/api/failures/{fid}/scenario")["geometry"]["route"]
        return fid

    @step("failure replays identically")
    def repro(fid: int):
        r = api.post(f"/api/failures/{fid}/repro")
        assert r["reproduced"], r["mismatches"]

    @step("template report")
    def report(fid: int):
        r = api.post(f"/api/failures/{fid}/report?llm=false")
        assert "## Reproduce" in r["markdown"] and "fgsim compare" in r["markdown"]
        assert api.get(f"/api/failures/{fid}/report")["id"] == r["id"]

    @step("metrics exposed")
    def metrics(cid: int):
        text = api.get("/metrics", raw=True)
        assert "fleetguard_db_up 1.0" in text
        assert f'campaign="{cid}"' in text

    @step("web UI and API proxy")
    def ui():
        assert "<div id=\"root\"></div>" in web.get("/", raw=True)
        assert "<div id=\"root\"></div>" in web.get("/failures/1", raw=True)  # client-side route
        assert web.get("/api/health")["status"] == "ok"

    t0 = time.monotonic()
    print(f"smoke test against {args.api} and {args.web}")
    try:
        health()
        cid = regression()
        clean()
        fid = triage(cid)
        repro(fid)
        report(fid)
        metrics(cid)
        ui()
    except (AssertionError, urllib.error.URLError, TimeoutError, KeyError) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(f"all good in {time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
