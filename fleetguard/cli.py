"""fleetguard command line."""

from __future__ import annotations

import argparse
import json
import sys

from . import db as fgdb
from . import repo
from .builds import Registry
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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
