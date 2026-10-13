# Changelog

## 0.2.0 (October 2026)

**Classifiers 2026.10**
- Latency is compared only over the time both drives were running, so a
  regression that changes drive length is no longer blamed on the planner.
- A watchdog trip without extra deadline misses is a disengagement (a policy
  change), not a latency regression.
- Seeded benchmark: 38/50 reproduced on a fresh seed range (300000+), same on the
  March seeds; 37/50 before. Details and every remaining miss in docs/RESULTS.md.

**Tooling**
- `fleetguard benchmark --seed-start`, classifier version recorded per run,
  `tools/bench_diff.py` to compare two runs case by case.
- "Copy summary" on the campaign page (markdown with links back to the UI).
- CI tests the Python package on 3.11 and 3.12.

**Fixed**
- Repository line endings normalized to LF (`.gitattributes`); the dashboard
  generator writes LF so the drift check is OS independent.

## 0.1.0 (June 2026)

First complete version.

**Simulator (`core/`, C++17)**
- Seven seeded scenario families, kinematic vehicle with actuator delay/lag/slew,
  perception model (misses, noise, tracker, phantoms, latency), IDM planner with
  a timing model and watchdog, pure-pursuit/PI control, safety-driver model.
- Deterministic replays and shared random draws between builds.
- Build-vs-build comparison aligned on arc length; parallel batch runner
  (about 4,000 drives/s on 22 threads), output independent of thread count.
- 109 GoogleTest tests, clean under ASan/UBSan; 105 pytest tests (against Postgres and the real fgsim) and 33 vitest tests for the UI.

**Platform (`fleetguard/`, Python + Postgres)**
- Campaigns, a SKIP LOCKED worker queue, COPY-based ingestion.
- SQL telemetry views and five SQL failure classifiers with time-based root-cause
  attribution, signature clustering and a per-category verdict.
- Exact replay verification of any failure (`fleetguard repro`).
- Seeded-regression benchmark: 37/50 reproduced on held-out seeds, 1/10 clean
  controls flagged.
- Diagnostic reports with optional LLM narratives (local Ollama by default),
  checked against the facts before use; one report per cluster after each campaign.
- `fleetguard gate` for release pipelines, markdown campaign summaries.
- FastAPI service with Prometheus metrics; Alertmanager webhook.

**Monitoring**
- Prometheus alert rules with promtool unit tests; Alertmanager -> API.
- Three provisioned Grafana dashboards generated from code.

**UI (`web/`, React + TypeScript)**
- Campaigns with live progress and alerts, campaign detail (KPI deltas,
  categories, clusters, per-family table, failures), failure detail (evidence,
  parameter diff, metrics, timeline, telemetry charts on a shared cursor,
  trajectory map with playback and follow mode, reports, replay verification),
  builds and parameter diffs. Served by nginx in compose.

**Fixed along the way**
- Classifier false positives on benign builds (event matching window, p99 over
  drives of different length, single oscillation episodes).
- Planner choosing nested loops right after bulk loads: classifier query 12.6 s
  -> 48 ms; a 100k-drive ingest from ten minutes to 26 s.
- nginx keeping a stale API container IP after the api service was recreated.
- A flaky UI test caused by prefix-matched fake routes.
