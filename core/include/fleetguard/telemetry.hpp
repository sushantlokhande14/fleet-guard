#pragma once

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace fg {

constexpr double kInf = std::numeric_limits<double>::infinity();

// One logged sample (10 Hz by default).
struct Frame {
  double t = 0;
  double x = 0, y = 0, yaw = 0;
  double v = 0, a = 0, steer = 0;
  double steer_cmd = 0, accel_cmd = 0;
  double s = 0;            // progress along the live route
  double cte = 0;          // cross-track error to the live lane centre
  double heading_err = 0;  // yaw minus lane heading
  double v_ref = 0;        // controller speed reference
  double target_speed = 0; // planner's free-road target
  int lead_id = -1;        // object the planner is reacting to
  double lead_gap = kInf;  // perceived gap to it
  double gt_gap = kInf;    // true gap to the nearest in-path object
  double ttc = kInf;       // true time to collision with it
  double planner_latency_ms = 0;
  int deadline_miss = 0;
  int n_tracks = 0;    // confirmed tracks reported by perception
  int n_relevant = 0;  // true objects in the ego corridor within 60 m
  int n_missed = 0;    // relevant objects with no confirmed track
  int n_phantom = 0;   // confirmed tracks with no real object behind them
  int engaged = 1;
};

struct Event {
  double t = 0;
  std::string kind;
  int severity = 1;  // 1 info, 2 warning, 3 critical
  double value = 0;
  double duration = 0;
  std::string detail;
};

struct DriveSummary {
  std::string scenario_id;
  std::string family;
  uint64_t seed = 0;
  std::string build;
  std::string weather;
  std::string outcome = "completed";  // completed | disengaged | collision | timeout
  std::string reason;                 // disengagement / collision cause
  double duration_s = 0;
  double distance_m = 0;
  double route_completion = 0;
  double mean_speed = 0;
  double cte_max = 0, cte_rms = 0, cte_p95 = 0;
  double heading_err_max = 0;
  double jerk_rms = 0;
  double accel_min = 0;
  double lat_acc_max = 0;
  double steer_reversal_rate = 0;  // per second
  double accel_reversal_rate = 0;  // per second
  double min_ttc = kInf;
  double min_gap = kInf;
  double planner_p50_ms = 0, planner_p99_ms = 0, planner_max_ms = 0;
  int planner_cycles = 0;
  int deadline_misses = 0;
  int det_tp = 0, det_fn = 0, det_fp = 0;
  double recall = 1.0, precision = 1.0;
  int hard_brakes = 0;
  int n_events = 0;
};

struct DriveResult {
  DriveSummary summary;
  std::vector<Frame> frames;
  std::vector<Event> events;
};

}  // namespace fg
