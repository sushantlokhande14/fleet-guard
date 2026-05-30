# Architecture notes

How Fleet Guard is put together and why. For results see [RESULTS.md](RESULTS.md).

## Pipeline

```
queue campaign (API/CLI)
  -> worker claims it (UPDATE ... FOR UPDATE SKIP LOCKED)
  -> fgsim batch: every scenario driven by baseline and candidate, in parallel
  -> JSONL + CSV on disk
  -> COPY into staging tables, INSERT ... SELECT into drives / events / pairs / telemetry
  -> 5 SQL classifiers -> attribution -> failures (one per scenario) -> clusters
  -> verdict per category -> cluster reports
  -> Prometheus scrape -> alert rules -> Alertmanager -> /api/alerts
```

A campaign is one baseline build, one candidate build and a scenario set
(families x seed range). Everything after the simulator is plain Postgres and
Python; the simulator is a separate C++ process behind a CLI so that any drive
the platform reports can be replayed by hand with the same command.

## Determinism and shared luck

Every random draw in fgsim comes from xoshiro256** streams seeded from the
scenario seed (`rng.hpp`), one stream per subsystem: scenario layout, sensor
noise, phantom detections, planner timing. Standard-library distributions are
avoided because their output differs between implementations.

Two consequences:

1. **Replays are exact.** A drive is a pure function of (family, seed, build).
   `fleetguard repro` re-runs a stored failure and compares outcome, every
   summary metric and the event timeline with what was ingested.
2. **Builds share their luck** (common random numbers). Perception draws are
   consumed in a fixed order per actor per tick whatever the outcome, and the
   planner draws its timing per cycle in a fixed order, so the baseline and the
   candidate see the same misses, the same phantoms and the same latency spikes
   until their behaviour diverges. A build with a higher miss rate misses a
   superset of what the baseline misses. That is what makes per-scenario
   comparison meaningful: a candidate identical to the baseline produces zero
   differences, not "noise within tolerance".

## The simulated stack

| module | model | regression knobs used by the benchmark |
|---|---|---|
| vehicle | kinematic bicycle, midpoint integration; actuators with transport delay, first-order lag, steering slew, friction cap | actuator delay |
| perception | range / FOV / weather-dependent misses, range-dependent position noise, alpha-beta tracks with confirm and coast, phantom clutter, latency pipeline | miss rates, far-pedestrian misses, weather range, range calibration, confirmation frames, clutter |
| planner | free-road speed from posted and curvature limits with preview; IDM interaction with the most constraining in-path track; cut-in prediction; pedestrian yield; timing model with deadline misses and a watchdog | headway, braking cap, prediction horizons, latency mean/jitter/spikes/per-object load, curve offset, lateral bias, stale map |
| control | pure pursuit on the rear axle, PI speed loop with feed-forward and jerk limit | steering gain, lookahead, speed gains |
| safety | safety-driver model: takeover on true TTC < 1 s or lane departure > 1.4 m; collision by oriented boxes | fixed across builds |

The safety model is deliberately not part of a build: every build is judged
by the same safety driver.

## Comparison

`compare.cpp` aligns the two drives on route arc length, not time, so a
slightly slower candidate is not "off course". It reports lateral and speed
differences, the time delta, the first point where behaviour diverges, and
candidate-minus-baseline deltas of every summary metric.

## Classification

Five SQL files in `fleetguard/classifiers/sql/` each emit a signal per scenario
pair when the candidate is worse in their dimension: disengagement (the baseline
completed, the candidate did not), latency spike, route deviation, perception
error, control instability. They work off two views: `pair_detail` (both drives
side by side) and `new_candidate_events` (candidate events with no same-kind
baseline event within 2 s; thanks to shared luck this is empty for identical
builds).

A failing scenario usually trips several signals: a missed pedestrian leads to
a late brake leads to a takeover. **Attribution** picks the root cause by time:
if the drive disengaged, the earliest signal at or before the takeover wins
(ties go upstream: perception before latency before control before route);
otherwise the earliest timed signal wins. Metric-only signals without a time can
only explain a takeover if they are strong.

Each failure gets a **signature** `category/family/key` (for example
`perception_error/ped_crossing/pedestrian`); failures sharing a signature are
treated as one probable bug.

The **verdict** flags a category at 3 or more failures and 5 or more per 1000
scenarios. Thresholds were calibrated only on clean builds (a candidate equal
to the baseline and a benign retune must produce zero failures), never on the
seeded regressions.

## Reports and the LLM guard

A report is built from facts in the database (`diagnostics/context.py`) into a
fixed markdown layout. An LLM (local Ollama by default, any OpenAI-compatible
endpoint) may write the summary, likely cause and next steps from the same
facts. Before a narrative is used, `diagnostics/guard.py` checks it:

- every parameter it blames must be in the build diff;
- every number it states must trace back to the facts, directly, as a
  percentage of a 0-1 fraction, or as a difference, ratio or percent change of a
  baseline/candidate pair.

A narrative that fails falls back to the deterministic text. Evidence, metrics,
the timeline and the repro command always come from data, never from the model.

## Storage notes

- Telemetry is stored only for flagged pairs, capped per campaign; any other
  pair is regenerated on demand because drives are deterministic.
- Ingest is COPY into temp staging tables followed by set-based joins. Both temp
  tables and freshly copied rows need `ANALYZE` before the joins and before the
  classifiers run, or the planner picks nested loops (seen at 700 and at 50,000
  scenarios; see the commit history).

## Known limits

- The stack is a model: no sensor physics, no multi-lane planning, no
  oncoming traffic. It is detailed enough to produce realistic regression
  signatures, not to validate a real vehicle.
- The seeded benchmark, the simulator and the classifiers share an author, so
  the benchmark measures the pipeline end to end rather than how it does on
  someone else's bugs.
- Categories are symptom based. A steering-gain bump that overshoots on bends
  without ringing is filed as a route deviation, which is defensible but counts
  as a miss against a "control" label.
