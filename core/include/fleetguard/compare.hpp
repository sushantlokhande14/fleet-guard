#pragma once

#include <nlohmann/json.hpp>
#include <string>

#include "fleetguard/telemetry.hpp"

namespace fg {

// How a candidate build's drive differs from the baseline's on the same scenario.
// Trajectories are aligned on route arc length, not time, so a candidate that is
// a little slower is not reported as "off course".
struct PairMetrics {
  std::string scenario_id;
  std::string baseline;
  std::string candidate;
  double common_s = 0.0;           // metres of route both drives covered
  double lat_mean_abs_diff = 0.0;  // mean |cte_cand - cte_base|
  double lat_max_abs_diff = 0.0;
  double speed_rmse = 0.0;         // speed difference at equal s
  double time_delta_s = 0.0;       // candidate minus baseline time to reach common_s
  double first_divergence_s = -1.0;
  double first_divergence_t = -1.0;  // candidate clock at that point
  bool outcome_changed = false;

  // candidate minus baseline
  double d_cte_max = 0.0;
  double d_jerk_rms = 0.0;
  double d_steer_reversal_rate = 0.0;
  double d_accel_reversal_rate = 0.0;
  double d_min_ttc = 0.0;  // TTC capped at 10 s on both sides
  double d_planner_p99_ms = 0.0;
  double d_recall = 0.0;
  double d_precision = 0.0;
  int d_deadline_misses = 0;
  int d_hard_brakes = 0;
};

struct CompareOptions {
  double ds = 1.0;              // resampling step (m)
  double diverge_lat = 0.3;     // m
  double diverge_speed = 1.5;   // m/s
};

PairMetrics compare_drives(const DriveResult& base, const DriveResult& cand, const CompareOptions& opt = {});
nlohmann::json pair_to_json(const PairMetrics& p);

}  // namespace fg
