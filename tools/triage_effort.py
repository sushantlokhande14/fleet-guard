"""How much there is to look at, with and without the platform.

Human triage time is not something this repo can measure. What it can measure is
the number of items an engineer has to open:

  without   every scenario where the candidate behaved differently from the
            baseline (fgsim flags the pair: different outcome, diverging path,
            new events, metric deltas)
  with      one report per failure cluster (same signature = same probable bug)

    python tools/triage_effort.py [--campaigns 2,90] [--benchmark RUN_ID]
"""

from __future__ import annotations

import argparse
import statistics

from fleetguard import db as fgdb

SQL = """
SELECT c.id, c.name, c.candidate, c.scenario_count,
       (SELECT count(*) FROM pairs p WHERE p.campaign_id = c.id AND p.flagged) AS flagged_pairs,
       (SELECT count(*) FROM drives d WHERE d.campaign_id = c.id AND d.role = 'candidate'
                                      AND d.outcome <> 'completed') AS failed_drives,
       (SELECT count(*) FROM failures f WHERE f.campaign_id = c.id) AS failures,
       (SELECT count(DISTINCT signature) FROM failures f WHERE f.campaign_id = c.id) AS clusters,
       c.verdict->>'status' AS verdict
  FROM campaigns c
 WHERE c.status = 'done' AND (%(ids)s::bigint[] IS NULL OR c.id = ANY(%(ids)s))
   AND (%(run)s::text IS NULL AND NOT (c.tags ? 'benchmark')
        OR c.tags->>'benchmark' = %(run)s AND c.tags->>'expected' <> 'clean')
 ORDER BY c.id
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaigns", help="comma separated ids (default: all non-benchmark)")
    ap.add_argument("--benchmark", metavar="RUN_ID", help="use the seeded-regression campaigns of one benchmark run")
    args = ap.parse_args()
    ids = [int(x) for x in args.campaigns.split(",")] if args.campaigns else None
    with fgdb.session() as conn:
        rows = [r for r in conn.execute(SQL, {"ids": ids, "run": args.benchmark}) if r["clusters"]]

    print("| campaign | scenarios | flagged pairs | failed candidate drives | classified failures | clusters "
          "| items saved |")
    print("|---|---|---|---|---|---|---|")
    saved = []
    for r in rows:
        s = 1 - r["clusters"] / r["flagged_pairs"] if r["flagged_pairs"] else 0.0
        saved.append(s)
        print(f"| #{r['id']} {r['candidate']} | {r['scenario_count']} | {r['flagged_pairs']} | "
              f"{r['failed_drives']} | {r['failures']} | {r['clusters']} | {100 * s:.0f}% |")
    if saved:
        print(f"\n{len(saved)} campaigns; items to open reduced by a median of {100 * statistics.median(saved):.0f}% "
              f"(min {100 * min(saved):.0f}%, max {100 * max(saved):.0f}%)")


if __name__ == "__main__":
    main()
