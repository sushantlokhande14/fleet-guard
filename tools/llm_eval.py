"""Measure LLM-written report narratives against the guard.

Picks the strongest failure of up to N clusters per category from finished
campaigns, asks the configured model (local Ollama by default) for a narrative,
and records whether the guard accepted it, why not if it did not, and how long
it took. Writes a markdown summary plus a few example reports.

    fleetguard db migrate
    FG_LLM_BASE_URL=http://host.docker.internal:11434/v1 python tools/llm_eval.py --per-category 6 --out docs/llm
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

from fleetguard import db as fgdb
from fleetguard.classifiers import CATEGORIES
from fleetguard.diagnostics import report
from fleetguard.diagnostics.llm import LLMClient


def pick(conn, per_category: int) -> list[dict]:
    rows = []
    for cat in CATEGORIES:
        rows += conn.execute(
            """
            SELECT DISTINCT ON (f.signature) f.id, f.category, f.signature, f.campaign_id, f.score
              FROM failures f JOIN campaigns c ON c.id = f.campaign_id
             WHERE f.category = %s AND c.status = 'done'
             ORDER BY f.signature, f.score DESC
            """,
            (cat,),
        ).fetchall()[:per_category]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=6)
    ap.add_argument("--out", default="docs/llm")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    llm = LLMClient()
    out = Path(args.out)
    (out / "examples").mkdir(parents=True, exist_ok=True)
    results = []
    with fgdb.session() as conn:
        picked = pick(conn, args.per_category)
        for i, f in enumerate(picked, 1):
            r = report.generate(conn, f["id"], llm=llm)
            conn.commit()
            meta = r["meta"]
            row = {"failure_id": f["id"], "category": f["category"], "signature": f["signature"],
                   "accepted": r["generator"] == "llm", "latency_s": meta.get("latency_s"),
                   "issues": meta.get("guard_issues", []), "error": meta.get("llm_error"),
                   "tokens": (meta.get("prompt_tokens"), meta.get("completion_tokens")), "markdown": r["markdown"]}
            results.append(row)
            print(f"[{i}/{len(picked)}] #{f['id']} {f['category']:20s} "
                  f"{'accepted' if row['accepted'] else 'REJECTED'} {row['latency_s']}s "
                  f"{'; '.join(row['issues'])[:100]}", flush=True)

    ok = [r for r in results if r["accepted"]]
    lat = [r["latency_s"] for r in results if r["latency_s"] is not None]
    by_cat = collections.defaultdict(lambda: [0, 0])
    reasons = collections.Counter()
    for r in results:
        by_cat[r["category"]][0] += r["accepted"]
        by_cat[r["category"]][1] += 1
        for issue in r["issues"]:
            reasons[issue.split(":")[0]] += 1
        if r["error"]:
            reasons["endpoint error"] += 1

    lines = [
        f"# LLM narratives vs the guard ({llm.model})",
        "",
        f"{len(results)} failures (strongest failure of up to {args.per_category} clusters per category), "
        f"narrative requested from `{llm.model}` at `{llm.base_url}`.",
        "",
        "| | |",
        "|---|---|",
        f"| narratives accepted by the guard | **{len(ok)} / {len(results)}** |",
        f"| median latency | {statistics.median(lat):.1f} s |" if lat else "| median latency | - |",
        f"| p90 latency | {sorted(lat)[int(0.9 * (len(lat) - 1))]:.1f} s |" if lat else "| p90 latency | - |",
        "",
        "| category | accepted |",
        "|---|---|",
        *[f"| {c} | {a} / {n} |" for c, (a, n) in sorted(by_cat.items())],
        "",
        "Guard findings (a narrative can have several; dropped suspects do not reject it):",
        "",
        *[f"- {k}: {v}" for k, v in reasons.most_common()],
        "",
        "Rejected narratives fall back to the deterministic template, so every failure still gets a report.",
    ]
    (out / "llm_eval.md").write_text("\n".join(lines) + "\n")
    (out / "llm_eval.json").write_text(json.dumps([{k: v for k, v in r.items() if k != "markdown"}
                                                   for r in results], indent=2))
    seen = set()
    for r in ok:
        if r["category"] in seen or len(seen) >= args.examples:
            continue
        seen.add(r["category"])
        (out / "examples" / f"{r['category']}-{r['failure_id']}.md").write_text(r["markdown"])
    print(f"accepted {len(ok)}/{len(results)}; wrote {out}/llm_eval.md")


if __name__ == "__main__":
    main()
