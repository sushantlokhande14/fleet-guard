"""fleetguard command line."""

from __future__ import annotations

import argparse
import json
import sys

from . import benchmark, campaigns, repo, repro
from . import db as fgdb
from .builds import Registry
from .config import get_settings
from .pipeline import post_process
from .sim import Fgsim


def cmd_builds(args: argparse.Namespace) -> int:
    sim = Fgsim()
    reg = Registry(defaults=sim.defaults())
    if args.action == "list":
        for name in reg.names():
            b = reg.get(name)
            parent = f" (from {b.parent})" if b.parent else ""
            print(f"{name}{parent}  {b.description}")
    elif args.action == "show":
        print(json.dumps(reg.effective(args.names[0]), indent=2))
    elif args.action == "sync":
        with fgdb.session() as conn:
            n = repo.sync_builds(conn, reg)
        print(f"synced {n} builds")
    elif args.action == "diff":
        if len(args.names) != 2:
            print("diff needs two build names", file=sys.stderr)
            return 2
        for c in reg.diff(args.names[0], args.names[1]):
            print(f"{c.key:40s} {c.baseline!s:>10} -> {c.candidate!s}")
    return 0


def cmd_db(args: argparse.Namespace) -> int:
    with fgdb.session() as conn:
        ran = fgdb.migrate(conn)
    print("applied: " + (", ".join(ran) if ran else "nothing, schema is current"))
    return 0


def _print_campaign(c: dict) -> None:
    pct = f"{100 * c['progress']:.0f}%"
    rate = f"{c['drives_per_second']:.0f} drives/s" if c["drives_per_second"] else ""
    print(f"#{c['id']:<5} {c['status']:<11} {pct:>5}  {c['candidate']} vs {c['baseline']}"
          f"  ({c['scenario_count']} scenarios) {rate}")


def cmd_campaign(args: argparse.Namespace) -> int:
    if args.action == "create":
        with fgdb.session() as conn:
            cid = campaigns.create(conn, baseline=args.baseline, candidate=args.candidate,
                                   scenario_count=args.count, seed_start=args.seed_start,
                                   families=args.families.split(",") if args.families else None)
        print(f"created campaign {cid}")
        if args.run:
            campaigns.run(cid, keep_files=args.keep_files, after_ingest=post_process)
            _print_verdict(cid)
    elif args.action == "run":
        campaigns.run(args.id, keep_files=args.keep_files, after_ingest=post_process)
        _print_verdict(args.id)
    elif args.action == "list":
        with fgdb.session() as conn:
            for c in campaigns.list_recent(conn):
                _print_campaign(c)
    elif args.action == "show":
        return _print_verdict(args.id)
    return 0


def _print_verdict(campaign_id: int) -> int:
    with fgdb.session() as conn:
        c = campaigns.get(conn, campaign_id)
    if c is None:
        print(f"no campaign {campaign_id}", file=sys.stderr)
        return 1
    _print_campaign(c)
    if c.get("timings"):
        print("timings: " + ", ".join(f"{k} {v:.1f}s" for k, v in c["timings"].items()))
    v = c["verdict"]
    if not v:
        return 0
    print(f"verdict: {v['status'].upper()}  ({v['failures']} failing scenarios of {v['scenarios']})")
    for cat, row in v["categories"].items():
        mark = "!!" if row["flagged"] else "  "
        rate = f"({row['per_1000']:.1f} per 1000, {row['critical']} critical)"
        print(f"  {mark} {cat:20s} {row['failures']:5d}  {rate}")
    if v["top_clusters"]:
        print("  top clusters:")
        for cl in v["top_clusters"][:5]:
            print(f"     {cl['n']:4d}  {cl['signature']}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    def show(r: dict) -> None:
        if r["category"] == "clean":
            verdict = "pass" if r["passed"] else "FALSE POSITIVE " + ",".join(r["flagged"])
        else:
            verdict = "reproduced" if r["reproduced"] else f"MISSED (flagged: {','.join(r['flagged']) or '-'})"
        print(f"{r['case']:45s} {verdict}", flush=True)

    result = benchmark.run(get_settings().database_url, scenario_count=args.count, case_filter=args.cases,
                           on_case=show)
    benchmark.write(result, args.out)
    s = result["summary"]
    print(f"\nreproduced {s['reproduced']['hit']}/{s['reproduced']['n']}"
          f" ({100 * s['reproduced']['rate']:.1f}%), top-1 {s['top1']['hit']}/{s['top1']['n']},"
          f" control false positives {s['controls']['false_positives']}/{s['controls']['n']}")
    print(f"wrote {args.out}/benchmark.md")
    return 0


def cmd_repro(args: argparse.Namespace) -> int:
    with fgdb.session() as conn:
        r = repro.verify(conn, args.failure_id)
    print(r["command"])
    print("reproduced" if r["reproduced"] else "NOT reproduced:\n  " + "\n  ".join(r["mismatches"]))
    return 0 if r["reproduced"] else 1


def cmd_report(args: argparse.Namespace) -> int:
    from .diagnostics import report
    from .diagnostics.llm import LLMClient

    client = LLMClient() if args.llm else None
    with fgdb.session() as conn:
        r = report.generate(conn, args.failure_id, llm=client)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(r["markdown"])
        print(f"wrote {args.out} ({r['generator']})")
    else:
        print(r["markdown"])
    for issue in r["meta"].get("guard_issues", []):
        print(f"guard: {issue}", file=sys.stderr)
    if "llm_error" in r["meta"]:
        print(f"llm: {r['meta']['llm_error']} (used the template)", file=sys.stderr)
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    """Run a campaign now and fail (exit 1) if the candidate regressed. For release pipelines."""
    from .summary import campaign_markdown

    with fgdb.session() as conn:
        cid = campaigns.create(conn, baseline=args.baseline, candidate=args.candidate, scenario_count=args.count,
                               seed_start=args.seed_start, name=f"gate {args.candidate}",
                               families=args.families.split(",") if args.families else None)
    campaigns.run(cid, after_ingest=post_process)
    with fgdb.session() as conn:
        md = campaign_markdown(conn, cid, ui_base=args.ui)
        verdict = campaigns.get(conn, cid)["verdict"]
    print(md)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:  # append: GITHUB_STEP_SUMMARY is shared
            f.write(md)
    return 1 if verdict["status"] == "regression" else 0


def cmd_worker(args: argparse.Namespace) -> int:
    from . import worker

    return worker.main(once=args.once, poll_s=args.poll, metrics_port=args.metrics_port)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("fleetguard.api:create_app", factory=True, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_exporter(args: argparse.Namespace) -> int:
    import threading

    from prometheus_client import start_http_server

    from .metrics import fleet_registry

    start_http_server(args.port, registry=fleet_registry())
    print(f"fleet metrics on :{args.port}/metrics", flush=True)
    threading.Event().wait()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fleetguard", description="Fleet Guard validation platform")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("builds", help="inspect the build registry")
    b.add_argument("action", choices=["list", "show", "diff", "sync"])
    b.add_argument("names", nargs="*")
    b.set_defaults(func=cmd_builds)

    d = sub.add_parser("db", help="database maintenance")
    d.add_argument("action", choices=["migrate"])
    d.set_defaults(func=cmd_db)

    c = sub.add_parser("campaign", help="create and run validation campaigns")
    csub = c.add_subparsers(dest="action", required=True)
    cc = csub.add_parser("create")
    cc.add_argument("--baseline", required=True)
    cc.add_argument("--candidate", required=True)
    cc.add_argument("--count", type=int, required=True, help="scenarios (each is driven by both builds)")
    cc.add_argument("--families", help="comma separated (default: all)")
    cc.add_argument("--seed-start", type=int, default=0)
    cc.add_argument("--run", action="store_true", help="run it now instead of leaving it for the worker")
    cc.add_argument("--keep-files", action="store_true")
    cr = csub.add_parser("run")
    cr.add_argument("id", type=int)
    cr.add_argument("--keep-files", action="store_true")
    csub.add_parser("list")
    cs = csub.add_parser("show")
    cs.add_argument("id", type=int)
    c.set_defaults(func=cmd_campaign)

    bm = sub.add_parser("benchmark", help="run the seeded-regression benchmark")
    bm.add_argument("--count", type=int, default=700, help="scenarios per case")
    bm.add_argument("--cases", default="", help="only cases whose id starts with this")
    bm.add_argument("--out", default="docs/benchmark")
    bm.set_defaults(func=cmd_benchmark)

    rp = sub.add_parser("repro", help="replay a failure and check it matches what was stored")
    rp.add_argument("failure_id", type=int)
    rp.set_defaults(func=cmd_repro)

    gt = sub.add_parser("gate", help="run a campaign now; exit 1 if the candidate regressed")
    gt.add_argument("--baseline", required=True)
    gt.add_argument("--candidate", required=True)
    gt.add_argument("--count", type=int, default=700)
    gt.add_argument("--families")
    gt.add_argument("--seed-start", type=int, default=0)
    gt.add_argument("--summary", help="append the markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY)")
    gt.add_argument("--ui", help="base URL of the UI, for links in the summary")
    gt.set_defaults(func=cmd_gate)

    rep = sub.add_parser("report", help="write a diagnostic report for one failure")
    rep.add_argument("failure_id", type=int)
    rep.add_argument("--llm", action="store_true", help="narrative from the configured LLM (local Ollama by default)")
    rep.add_argument("--out", help="write markdown here instead of stdout")
    rep.set_defaults(func=cmd_report)

    wk = sub.add_parser("worker", help="run queued campaigns")
    wk.add_argument("--once", action="store_true", help="drain the queue and exit")
    wk.add_argument("--poll", type=float, default=2.0, help="seconds between queue polls")
    wk.add_argument("--metrics-port", type=int, default=0, help="serve worker metrics on this port")
    wk.set_defaults(func=cmd_worker)

    sv = sub.add_parser("serve", help="run the HTTP API (also serves /metrics)")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(func=cmd_serve)

    ex = sub.add_parser("exporter", help="serve fleet KPIs from the database as Prometheus metrics")
    ex.add_argument("--port", type=int, default=9102)
    ex.set_defaults(func=cmd_exporter)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
