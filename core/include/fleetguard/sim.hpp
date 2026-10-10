#pragma once

#include "fleetguard/build_config.hpp"
#include "fleetguard/scenario.hpp"
#include "fleetguard/telemetry.hpp"

namespace fg {

struct SimOptions {
  double dt = 0.05;    // 20 Hz physics and control
  int log_every = 2;   // log at 10 Hz
  bool record_frames = true;

  // safety-driver model; fixed across builds so every build is judged alike
  double ttc_takeover = 1.0;       // s
  double takeover_gap_max = 40.0;  // m
  double lane_departure_m = 1.4;   // |cross-track error| that ends autonomy
};

// Drive one scenario with one build. Fully deterministic in (scenario, build).
DriveResult run_drive(const Scenario& sc, const BuildConfig& build, const SimOptions& opt = {});

// helpers shared with the metrics code
double percentile(std::vector<double> v, double p);

}  // namespace fg
