import json
import os

import httpx
import pytest

from fleetguard import campaigns, repo
from fleetguard import db as fgdb
from fleetguard.builds import Registry
from fleetguard.diagnostics import report, template
from fleetguard.diagnostics.context import build_context
from fleetguard.diagnostics.llm import LLMClient
from fleetguard.pipeline import post_process
from fleetguard.sim import Fgsim

pytestmark = pytest.mark.fgsim


@pytest.fixture(scope="module")
def failed_campaign(tmp_path_factory):
    """One rc1 campaign shared by every test in this module (they only read)."""
    url = os.environ.get("FG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("FG_TEST_DATABASE_URL not set")
    sim = Fgsim()
    conn = fgdb.connect(url)
    fgdb.reset(conn)
    fgdb.migrate(conn)
    repo.sync_builds(conn, Registry(defaults=sim.defaults()))
    cid = campaigns.create(conn, baseline="drive-2.3.0", candidate="drive-2.4.0-rc1", scenario_count=140)
    conn.commit()
    campaigns.run(cid, url=url, sim=sim, threads=4, runs_dir=tmp_path_factory.mktemp("runs"),
                  after_ingest=post_process)
    yield conn, cid
    conn.close()


def strongest(conn, cid, category=None):
    row = conn.execute(
        "SELECT id FROM failures WHERE campaign_id = %s AND (%s::text IS NULL OR category = %s)"
        " ORDER BY severity DESC, score DESC LIMIT 1", (cid, category, category)).fetchone()
    return row["id"]


def test_context_has_the_facts(failed_campaign):
    conn, cid = failed_campaign
    ctx = build_context(conn, strongest(conn, cid, "control_instability"))
    assert ctx.campaign_id == cid and ctx.candidate == "drive-2.4.0-rc1"
    assert ctx.category == "control_instability"
    assert {m["key"] for m in ctx.metrics} >= {"steer_reversal_rate", "recall", "planner_p99_ms"}
    assert {d["key"] for d in ctx.build_diff} == {"control.steer_gain", "control.actuator_delay_ms",
                                                  "planner.latency_per_object_ms"}
    assert ctx.cluster["size"] >= 1 and ctx.cluster["campaign_failures"] >= ctx.cluster["size"]
    assert ctx.repro_command.count("fgsim compare") == 1
    assert all(e["role"] in ("baseline", "candidate") for e in ctx.timeline)
    json.dumps(ctx.facts())  # serialisable for the LLM


def test_timeline_is_ordered_and_bounded(failed_campaign):
    conn, cid = failed_campaign
    ctx = build_context(conn, strongest(conn, cid), timeline_limit=5)
    ts = [e["t"] for e in ctx.timeline]
    assert ts == sorted(ts) and len(ts) <= 5


def test_unknown_failure(failed_campaign):
    conn, _ = failed_campaign
    with pytest.raises(LookupError):
        build_context(conn, 10**9)


def test_template_report_every_category(failed_campaign):
    conn, cid = failed_campaign
    cats = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM failures WHERE campaign_id = %s", (cid,))]
    assert "control_instability" in cats
    for cat in cats:
        ctx = build_context(conn, strongest(conn, cid, cat))
        md = template.render(ctx)
        for section in ("## Summary", "## Likely cause", "## What changed", "## Evidence", "## Metrics",
                        "## Timeline", "## Reproduce", "## Next steps"):
            assert section in md, (cat, section)
        assert ctx.repro_command in md
        assert ctx.candidate in md and ctx.baseline in md


def test_template_points_at_the_right_parameters(failed_campaign):
    conn, cid = failed_campaign
    ctx = build_context(conn, strongest(conn, cid, "control_instability"))
    keys = {d["key"] for d in template.suspects(ctx)}
    assert keys == {"control.steer_gain", "control.actuator_delay_ms"}
    assert "`control.actuator_delay_ms` (40 -> 95)" in template.default_cause(ctx)


def test_narrative_replaces_only_prose(failed_campaign):
    conn, cid = failed_campaign
    ctx = build_context(conn, strongest(conn, cid))
    md = template.render(ctx, {"summary": "SUMMARY-X", "likely_cause": "CAUSE-Y", "next_steps": ["STEP-Z"]},
                         generator="llm")
    assert "SUMMARY-X" in md and "CAUSE-Y" in md and "1. STEP-Z" in md
    assert "## Metrics" in md and ctx.repro_command in md
    assert "(llm)" in md


def fake_llm(payload):
    """LLM client whose endpoint answers with a fixed JSON object."""
    def handler(request):
        body = {"model": "fake-7b", "choices": [{"message": {"content": json.dumps(payload)}}]}
        return httpx.Response(200, json=body)

    return LLMClient(base_url="http://fake/v1", model="fake-7b", transport=httpx.MockTransport(handler))


def test_report_template_only(failed_campaign):
    conn, cid = failed_campaign
    fid = strongest(conn, cid)
    r = report.generate(conn, fid)
    assert r["generator"] == "template" and r["model"] is None and r["narrative"] is None
    assert report.latest(conn, fid)["id"] == r["id"]


def test_report_with_grounded_llm_narrative(failed_campaign):
    conn, cid = failed_campaign
    fid = strongest(conn, cid, "control_instability")
    ctx = build_context(conn, fid)
    b, c = ctx.evidence["steer_reversals_per_s"]
    good = {"summary": f"Steering reversals rose from {b}/s to {c}/s on {ctx.scenario['id']}.",
            "likely_cause": "The added actuator delay (control.actuator_delay_ms) makes the steering loop ring.",
            "suspect_parameters": ["control.actuator_delay_ms"],
            "next_steps": ["Revert the delay and re-run the cluster."], "confidence": "medium"}
    r = report.generate(conn, fid, llm=fake_llm(good))
    assert r["generator"] == "llm" and r["model"] == "fake-7b"
    assert good["summary"] in r["markdown"] and "(llm, fake-7b)" in r["markdown"]
    assert r["narrative"]["suspect_parameters"] == ["control.actuator_delay_ms"]


def test_report_rejects_hallucination_and_falls_back(failed_campaign):
    conn, cid = failed_campaign
    fid = strongest(conn, cid, "control_instability")
    bad = {"summary": "Steering reversals rose by 812%.", "likely_cause": "planner.headway_s was cut.",
           "next_steps": ["x"]}
    r = report.generate(conn, fid, llm=fake_llm(bad))
    assert r["generator"] == "template"
    assert r["meta"]["llm_rejected"] is True
    assert any("planner.headway_s" in i for i in r["meta"]["guard_issues"])
    assert "812" not in r["markdown"]


def test_report_survives_llm_outage(failed_campaign):
    conn, cid = failed_campaign
    down = LLMClient(base_url="http://127.0.0.1:9/v1", timeout_s=1)
    r = report.generate(conn, strongest(conn, cid), llm=down)
    assert r["generator"] == "template" and "unreachable" in r["meta"]["llm_error"]


def test_cluster_members_listed(failed_campaign):
    conn, cid = failed_campaign
    sig = conn.execute("SELECT signature FROM failures WHERE campaign_id = %s GROUP BY signature"
                       " ORDER BY count(*) DESC LIMIT 1", (cid,)).fetchone()["signature"]
    fid = conn.execute("SELECT id FROM failures WHERE campaign_id = %s AND signature = %s ORDER BY score DESC"
                       " LIMIT 1", (cid, sig)).fetchone()["id"]
    ctx = build_context(conn, fid)
    others = ctx.cluster["others"]
    assert len(others) == min(10, ctx.cluster["size"] - 1)
    assert fid not in {o["id"] for o in others}
    md = template.render(ctx)
    assert "## Same signature" in md
    if others:
        assert f"#{others[0]['id']}" in md
