# Results

Measured numbers only. Everything here can be regenerated with the commands shown.

## Seeded-regression benchmark (March)

```bash
docker compose run --rm migrate fleetguard benchmark --count 700 --out docs/benchmark
```

50 injected regressions (5 mechanisms x 2 magnitudes x 5 categories, see
`fleetguard/seeded.py`) and 10 clean controls. Each is a full campaign against
`drive-2.3.0` over 700 scenarios (100 per family) from seed 50000 onward. The
classifier thresholds were calibrated on seeds below 1000, and only against clean
builds, never against seeded ones.

A case counts as **reproduced** when the campaign verdict flags the injected
category *and* the strongest failure in that category replays identically
(`fleetguard repro`: same outcome, metrics and event timeline from the scenario
seed and the two build definitions).

| | result |
|---|---|
| seeded regressions reproduced | **37 / 50 (74%)** |
| injected category ranked first | 35 / 50 |
| clean controls flagged | 1 / 10 |
| simulated drives | 84,000 |

Per case: [benchmark/benchmark.md](benchmark/benchmark.md).

By category: perception 7/10, latency 10/10, route 8/10, control 5/10, disengagement 7/10.
Severe 21/25, moderate 16/25.

### Why the 13 misses were missed

- **Different symptom than the label** (5). `steer_gain` (both levels) overshoots
  on bends without ringing, so it is flagged as route deviation, not control.
  `gentle_curve_offset.moderate` switches its offset on and off on gentle bends
  often enough to show up as steering reversals (control) before the cross-track
  error crosses its floor, and `lateral_bias.subtle` (0.15 m) never reaches the
  0.45 m floor at all; what it does trip is extra steering reversals. `headway.moderate` makes following
  jerkier long before it causes takeovers. The categories are symptom based, so
  these are arguably right answers to a different question, but they count as
  misses here.
- **Below the noise floor** (6). `range_calibration` (both levels) changes the
  following gap by a few percent and never drops recall (the moderate one did
  trip 4 control flags instead); `slow_confirmation.moderate`,
  `short_lookahead.moderate` and `integral.moderate` produce 2 failures each, under
  the 3-failure / 5-per-1000 flag threshold; `watchdog.moderate` produced 1.
- **Wrong attribution** (2). `watchdog.severe` (disengage on the first deadline
  miss) produced 466 failures, all attributed to `latency_spike`: the classifier
  treats any new watchdog trip as a latency signal even when the candidate missed
  no more deadlines than the baseline. `integral.severe` changes drive length,
  and the latency classifier compares spike counts over drives of different
  lengths. Both are classifier bugs, noted for the next iteration.
- **Clean control flagged** (1). `position_noise` (sigma 0.12 to 0.13 m) shifted
  enough braking to produce 5 control-instability failures over 700 scenarios,
  just over the threshold.

Same-author caveat: the regressions, the simulator and the classifiers were all
written by the same person, so this measures the pipeline end to end, not how it
would do on someone else's bugs.

## Scale: one 100,000-drive campaign (May)

```bash
docker compose run --rm migrate fleetguard campaign create     --baseline drive-2.3.0 --candidate drive-2.4.0-rc1 --count 50000 --seed-start 100000 --run
```

50,000 scenarios x 2 builds through the whole pipeline (worker, fgsim batch,
COPY ingest, SQL classifiers, verdict, cluster reports) on a 22-thread desktop:

| phase | wall time |
|---|---|
| simulate (fgsim, 22 threads) | 24.2 s (4,134 drives/s) |
| ingest (100,000 drives, 232,069 events, 421,833 telemetry frames) | 25.7 s |
| classify + verdict + cluster reports | 2.2 s |
| end to end | 52.1 s |

Verdict: regression in latency_spike (112 per 1000 scenarios) and
control_instability (142 per 1000), the same two categories and nearly the same
rates as the 700-scenario campaign, with 70 disengagements (1.4 per 1000) staying
under the flag threshold.

The first attempt at this size spent ten minutes in one join during ingest:
temp staging tables have no statistics, so Postgres picked nested loops. The fix
(ANALYZE right after each COPY) is in `fleetguard/ingest.py`.

## Triage workload (proxy, April)

```bash
python tools/triage_effort.py --campaigns 2,90
python tools/triage_effort.py --benchmark a8c10ffd
```

Human triage time was not measured; this project has no triage engineers to
time. What can be counted is how many items someone has to open. Without the
platform, that is every scenario where the candidate behaved differently from
the baseline (fgsim flags the pair). With it, it is one report per failure
cluster.

| campaign | scenarios | flagged pairs | failed candidate drives | classified failures | clusters | items saved |
|---|---|---|---|---|---|---|
| #2 drive-2.4.0-rc1 | 700 | 208 | 12 | 185 | 10 | 95% |
| #90 drive-2.4.0-rc2 | 700 | 160 | 12 | 64 | 6 | 96% |

Over the 50 seeded-regression campaigns the median reduction is 98% (59% to 99%).
Two things this does not show: reading a report takes longer than glancing at a
pass/fail line, and a cluster can hide a second bug that happens to share a
signature. Each report comes with the evidence, the parameter diff, the event
timeline and a verified repro command that would otherwise be pulled together by hand.
