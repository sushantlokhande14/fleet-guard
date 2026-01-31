# Fleet Guard

A validation platform for autonomous-driving software builds.

The idea: take two builds of a driving stack (a known-good baseline and a release
candidate), replay the same set of driving scenarios through both, and compare what
they did across trajectory, perception, planning and control signals. Anything the
candidate does worse gets classified, stored, and turned into a report an engineer
can reproduce.

## Status

The C++ core (`core/`) can generate scenarios and drive them closed loop:

- 7 seeded scenario families: `highway_follow`, `urban_cut_in`, `ped_crossing`,
  `s_curve`, `intersection_turn`, `construction_shift`, `stop_and_go`
- kinematic bicycle vehicle with actuator delay, lag, slew and friction limits
- perception model (range/FOV/weather misses, tracker, phantoms, latency) scored
  against ground truth every tick
- free-road planner, pure-pursuit + PI controller
- safety-driver model (TTC and lane-departure takeovers), collision detection, and
  event detectors (off-route, hard brake, oscillation, perception miss, phantom)

Still to come: object-aware planning, build-vs-build comparison, batch runs, the
Python side (campaigns, Postgres, classifiers), dashboards and a UI.

## Build

The core builds with CMake (C++17, nlohmann-json, GoogleTest). Easiest is the
toolchain image:

```bash
docker build --target toolchain -t fleetguard-toolchain .
docker run --rm -v "$PWD:/src" fleetguard-toolchain \
  bash -c "cmake -S core -B build -G Ninja && cmake --build build && ctest --test-dir build"
```

## fgsim

```bash
fgsim families
fgsim scenario --family urban_cut_in --seed 42 --geometry
fgsim run --family urban_cut_in --seed 42 --frames drive.csv --events
fgsim run --family urban_cut_in --seed 42 --build my_build.json
```

A build file only lists what differs from the defaults (`fgsim defaults` prints them):

```json
{ "name": "rc-1", "planner": { "headway_s": 1.2 }, "control": { "steer_gain": 1.3 } }
```

Every drive is deterministic in (family, seed, build).
