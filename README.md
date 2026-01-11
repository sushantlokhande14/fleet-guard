# Fleet Guard

A validation platform for autonomous-driving software builds.

The idea: take two builds of a driving stack (a known-good baseline and a release
candidate), replay the same set of driving scenarios through both, and compare what
they did across trajectory, perception, planning and control signals. Anything the
candidate does worse gets classified, stored, and turned into a report an engineer
can reproduce.

## Plan

- `core/` - C++ scenario simulator and comparison engine (`fgsim`)
- Python orchestration: campaigns, ingestion into Postgres, failure classifiers
- Prometheus metrics + alerts, Grafana dashboards
- Diagnostic reports for failed scenarios
- Web UI for triage and replay

Work in progress.
