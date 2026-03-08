"""fleetguard command line."""

from __future__ import annotations

import argparse
import json
import sys

from . import campaigns, repo
from . import db as fgdb
from .builds import Registry
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
