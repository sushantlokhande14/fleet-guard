"""Compare two seeded-benchmark runs case by case.

    python tools/bench_diff.py docs/benchmark/2026-03/benchmark.json docs/benchmark/2026-10-seeds-50000/benchmark.json

Lists every case whose outcome or flagged categories changed, then the summary
deltas. Useful after any classifier change: the same seeds before and after.
"""

from __future__ import annotations

import argparse
import json


def outcome(case: dict) -> str:
    if case["category"] == "clean":
        return "pass" if case["passed"] else "FALSE POSITIVE"
    return "reproduced" if case["reproduced"] else "missed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    args = ap.parse_args()
    a, b = (json.load(open(p)) for p in (args.before, args.after))
    before = {c["case"]: c for c in a["cases"]}
    after = {c["case"]: c for c in b["cases"]}

    def label(run: dict) -> str:
        return f"{run['run_id']} (seeds {run['seed_start']}+, classifiers {run.get('classifier_version', '?')})"

    print(f"before: {label(a)}\nafter:  {label(b)}\n")
    changed = 0
    for case_id in sorted(set(before) | set(after)):
        x, y = before.get(case_id), after.get(case_id)
        if x is None or y is None:
            print(f"  {case_id}: only in {'after' if x is None else 'before'}")
            changed += 1
            continue
        if outcome(x) != outcome(y) or x["flagged"] != y["flagged"]:
            changed += 1
            print(f"  {case_id}")
            print(f"      {outcome(x):14s} flagged {','.join(x['flagged']) or '-'}")
            print(f"   -> {outcome(y):14s} flagged {','.join(y['flagged']) or '-'}")
    if not changed:
        print("  no case changed")

    sa, sb = a["summary"], b["summary"]
    print()
    for key in ("reproduced", "top1", "detected", "repro_ok"):
        print(f"{key:10s} {sa[key]['hit']}/{sa[key]['n']} -> {sb[key]['hit']}/{sb[key]['n']}")
    print(f"controls   {sa['controls']['false_positives']}/{sa['controls']['n']} false positives -> "
          f"{sb['controls']['false_positives']}/{sb['controls']['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
