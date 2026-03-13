"""Seeded-regression benchmark.

For every case in fleetguard.seeded, run a full campaign of the baseline against
"baseline + injected bug" and score it:

  reproduced  the campaign verdict flags the injected category AND the strongest
              failure in that category replays identically from its seed and
              build definitions (fleetguard.repro.verify)
  top-1       the most frequent flagged category is the injected one
  controls    clean changes must come back "pass"

Scenarios come from a seed range the classifiers were never calibrated on.
"""

from __future__ import annotations

import collections
import json
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import campaigns, repo, repro, seeded
from . import db as fgdb
from .builds import deep_merge
from .pipeline import post_process
from .sim import Fgsim

HELD_OUT_SEED_START = 50_000  # calibration used seeds < 1,000
BASELINE = "drive-2.3.0"


def run_case(url: str, sim: Fgsim, case: seeded.SeededCase, *, scenario_count: int, run_id: str,
             threads: int | None = None) -> dict[str, Any]:
    name = f"seeded/{case.id}"
    with fgdb.session(url) as conn:
        base = repo.get_build(conn, BASELINE)
        overrides = deep_merge(base["overrides"], case.overrides)
        overrides["name"] = name
        params = deep_merge(sim.defaults(), overrides)
        repo.upsert_build(conn, name, overrides, params, description=case.mechanism, parent=BASELINE)
        cid = campaigns.create(conn, baseline=BASELINE, candidate=name, scenario_count=scenario_count,
                               seed_start=HELD_OUT_SEED_START, name=f"benchmark {case.id}",
                               tags={"benchmark": run_id, "case": case.id, "expected": case.category})
    t0 = time.monotonic()
    campaigns.run(cid, url=url, sim=sim, threads=threads, after_ingest=post_process)
    with fgdb.session(url) as conn:
        v = campaigns.get(conn, cid)["verdict"]
        row: dict[str, Any] = {
            "case": case.id, "category": case.category, "level": case.level, "mechanism": case.mechanism,
            "campaign_id": cid, "status": v["status"], "flagged": v["flagged"], "top_category": v["top_category"],
            "failures": v["failures"], "seconds": round(time.monotonic() - t0, 1),
        }
        if case.category == "clean":
            row["passed"] = v["status"] == "pass"
            return row
        row["category_failures"] = v["categories"][case.category]["failures"]
        row["detected"] = case.category in v["flagged"]
        row["top1"] = v["top_category"] == case.category
        strongest = conn.execute(
            "SELECT id FROM failures WHERE campaign_id = %s AND category = %s ORDER BY score DESC, id LIMIT 1",
            (cid, case.category)).fetchone()
        row["repro_ok"] = bool(strongest) and repro.verify(conn, strongest["id"], sim)["reproduced"]
        row["reproduced"] = row["detected"] and row["repro_ok"]
    return row


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    regs = [r for r in rows if r["category"] != "clean"]
    ctrls = [r for r in rows if r["category"] == "clean"]

    def rate(xs: list[dict], key: str) -> dict[str, Any]:
        n = len(xs)
        k = sum(1 for x in xs if x[key])
        return {"n": n, "hit": k, "rate": round(k / n, 4) if n else None}

    by_cat = collections.defaultdict(list)
    by_level = collections.defaultdict(list)
    for r in regs:
        by_cat[r["category"]].append(r)
        by_level[r["level"]].append(r)
    return {
        "reproduced": rate(regs, "reproduced"),
        "detected": rate(regs, "detected"),
        "top1": rate(regs, "top1"),
        "repro_ok": rate(regs, "repro_ok"),
        "by_category": {c: rate(xs, "reproduced") for c, xs in sorted(by_cat.items())},
        "by_level": {lv: rate(xs, "reproduced") for lv, xs in sorted(by_level.items())},
        "controls": {"n": len(ctrls), "false_positives": sum(1 for r in ctrls if not r["passed"])},
        "missed": [r["case"] for r in regs if not r["reproduced"]],
    }


def run(url: str, *, scenario_count: int = 700, case_filter: str = "", threads: int | None = None,
        sim: Fgsim | None = None, on_case: Callable[[dict], None] | None = None) -> dict[str, Any]:
    sim = sim or Fgsim()
    run_id = uuid.uuid4().hex[:8]
    cases = [c for c in seeded.all_cases() if c.id.startswith(case_filter)]
    rows = []
    for case in cases:
        row = run_case(url, sim, case, scenario_count=scenario_count, run_id=run_id, threads=threads)
        rows.append(row)
        if on_case:
            on_case(row)
    return {
        "run_id": run_id,
        "scenarios_per_case": scenario_count,
        "seed_start": HELD_OUT_SEED_START,
        "drives": 2 * scenario_count * len(cases),
        "cases": rows,
        "summary": summarize(rows),
    }


def to_markdown(result: dict[str, Any]) -> str:
    s = result["summary"]
    lines = [
        f"Benchmark run `{result['run_id']}`: {len(result['cases'])} campaigns, "
        f"{result['scenarios_per_case']} scenarios each (seeds from {result['seed_start']}), "
        f"{result['drives']:,} simulated drives.",
        "",
        "| | result |",
        "|---|---|",
        f"| seeded regressions reproduced | **{s['reproduced']['hit']} / {s['reproduced']['n']} "
        f"({100 * s['reproduced']['rate']:.0f}%)** |",
        f"| injected category flagged | {s['detected']['hit']} / {s['detected']['n']} |",
        f"| injected category ranked first | {s['top1']['hit']} / {s['top1']['n']} |",
        f"| strongest failure replayed identically | {s['repro_ok']['hit']} / {s['repro_ok']['n']} |",
        f"| clean controls flagged (false positives) | {s['controls']['false_positives']} / {s['controls']['n']} |",
        "",
        "| case | level | flagged | top category | failures | reproduced |",
        "|---|---|---|---|---|---|",
    ]
    for r in result["cases"]:
        if r["category"] == "clean":
            lines.append(f"| {r['case']} | control | {', '.join(r['flagged']) or '-'} | {r['top_category'] or '-'} "
                         f"| {r['failures']} | {'pass' if r['passed'] else 'FALSE POSITIVE'} |")
        else:
            lines.append(f"| {r['case']} | {r['level']} | {', '.join(r['flagged']) or '-'} "
                         f"| {r['top_category'] or '-'} | {r['category_failures']} / {r['failures']} "
                         f"| {'yes' if r['reproduced'] else 'no'} |")
    return "\n".join(lines) + "\n"


def write(result: dict[str, Any], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps(result, indent=2, default=str))
    (out / "benchmark.md").write_text(to_markdown(result))
