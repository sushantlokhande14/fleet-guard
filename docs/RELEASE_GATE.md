# Gating a release on a campaign

`fleetguard gate` runs a campaign of a candidate build against the current
release and exits non-zero if the verdict is a regression, so it can sit in a
release pipeline. The markdown it prints (and appends to `--summary`) is the
same as `GET /api/campaigns/{id}/summary.md`.

```bash
fleetguard gate --baseline drive-2.3.0 --candidate drive-2.4.0-rc3 --count 700 \
    --summary "$GITHUB_STEP_SUMMARY" --ui https://fleetguard.internal
```

## GitHub Actions

A sketch of a workflow that validates a build definition when it changes (not
part of this repo's CI; adapt names and paths). It brings up only what the gate
needs, Postgres plus the runtime image with fgsim:

```yaml
name: validate-build
on:
  pull_request:
    paths: ["builds/**"]

jobs:
  gate:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Database and builds
        run: |
          docker compose up -d --wait db
          docker compose run --rm migrate          # migrations + builds sync
      - name: Campaign
        run: |
          candidate=$(git diff --name-only origin/main -- builds | head -1 | xargs basename -s .json)
          docker compose run --rm -v "$GITHUB_STEP_SUMMARY:/summary.md" migrate \
            fleetguard gate --baseline drive-2.3.0 --candidate "$candidate" --count 700 --summary /summary.md
```

On a hosted 4-core runner a 700-scenario campaign (1,400 drives) simulates in
a few seconds; most of the job is building the image.

## Example output

For `drive-2.4.0-rc1` (exit code 1):

```markdown
## Fleet Guard #2: drive-2.4.0-rc1 vs drive-2.3.0: **REGRESSION**

700 scenarios x 2 builds = 1,400 drives, 185 failing scenarios.

| category | failures | per 1000 scenarios | flagged |
|---|---|---|---|
| disengagement | 3 | 4.29 |  |
| latency_spike | 76 | 108.57 | yes |
| route_deviation | 0 | 0.0 |  |
| perception_error | 0 | 0.0 |  |
| control_instability | 106 | 151.43 | yes |
```

For `drive-2.4.0-rc3` the verdict is PASS with 0 failing scenarios and the
command exits 0.
