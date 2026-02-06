#pragma once

#include <nlohmann/json.hpp>
#include <string>

#include "fleetguard/controller.hpp"

namespace fg {

// A "software build" is the full parameter set of the driving stack. Two builds
// differ the way two releases differ: tuned gains, a changed timeout, a module
// that got slower. Regressions are seeded by editing these values.
struct PerceptionParams {
  double range_m = 90.0;
  double fov_deg = 120.0;
  double vehicle_miss_rate = 0.02;  // per-frame miss probability at short range
  double ped_miss_rate = 0.04;
  double range_miss_slope = 0.0015;  // added miss probability per metre beyond 30 m
  double ped_far_miss_add = 0.0;     // extra pedestrian miss probability beyond ped_far_range_m
  double ped_far_range_m = 25.0;
  double rain_range_scale = 0.80;
  double fog_range_scale = 0.55;
  double rain_miss_add = 0.02;
  double fog_miss_add = 0.05;
  double pos_noise_m = 0.12;        // position noise sigma at zero range
  double pos_noise_per_m = 0.004;   // sigma growth with range
  double range_scale = 1.0;         // calibration: measured range = true range * scale
  double fp_rate = 0.0008;          // per-frame probability of a phantom detection
  int fp_max_frames = 3;            // longest a phantom persists
  double latency_ms = 60.0;         // sensor-to-track latency
  int confirm_frames = 2;           // detections before a track is reported
  int coast_frames = 5;             // missed frames before a track is dropped
};

struct PlannerParams {
  double cycle_ms = 100.0;  // planner period; a cycle slower than this misses its deadline
  double latency_mean_ms = 32.0;
  double latency_jitter_ms = 6.0;
  double latency_per_object_ms = 0.4;
  double spike_prob = 0.003;
  double spike_ms = 120.0;
  int watchdog_misses = 3;  // consecutive deadline misses before the stack disengages

  double headway_s = 1.5;
  double min_gap_m = 4.0;
  double max_accel = 1.8;
  double comfort_decel = 2.5;
  double max_decel = 7.5;
  double speed_gain = 0.6;
  double lat_accel_max = 2.2;
  double lateral_margin_m = 0.4;  // clearance beyond both half-widths for "in my path"

  bool predict_cut_ins = true;
  double cut_in_horizon_s = 2.0;
  bool yield_to_crossing_peds = true;
  double ped_horizon_s = 4.0;

  bool use_live_lane = true;         // false: follow the prior map even where the lane moved
  double curve_offset_m = 0.0;       // lateral offset applied on tight curves (map bug knob)
  double curve_offset_kappa = 0.012; // curvature above which curve_offset_m applies
  double lateral_bias_m = 0.0;       // constant lateral bias (calibration knob)
};

struct BuildConfig {
  std::string name = "baseline";
  PerceptionParams perception;
  PlannerParams planner;
  ControllerParams control;
};

// Overlay a JSON document onto the defaults. Unknown sections or keys throw:
// a typo in a regression definition must fail loudly, not silently test nothing.
BuildConfig build_from_json(const nlohmann::json& j);
nlohmann::json build_to_json(const BuildConfig& b);

}  // namespace fg
