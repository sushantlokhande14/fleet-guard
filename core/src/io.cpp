#include "fleetguard/io.hpp"

#include <cmath>
#include <cstdio>

namespace fg {

namespace {

// JSON has no infinity; "no lead / no conflict" is written as null
nlohmann::json finite_or_null(double v) { return std::isfinite(v) ? nlohmann::json(v) : nlohmann::json(nullptr); }

void put(std::ostream& os, double v, const char* fmt = "%.4f") {
  if (!std::isfinite(v)) return;  // empty CSV cell
  char buf[48];
  std::snprintf(buf, sizeof buf, fmt, v);
  os << buf;
}

}  // namespace

const char* frame_csv_header() {
  return "t,x,y,yaw,v,a,steer,steer_cmd,accel_cmd,s,cte,heading_err,v_ref,target_speed,"
         "lead_id,lead_gap,gt_gap,ttc,planner_latency_ms,deadline_miss,n_tracks,n_relevant,"
         "n_missed,n_phantom,engaged";
}

void write_frame_csv(std::ostream& os, const Frame& f) {
  put(os, f.t, "%.2f");
  os << ',';
  put(os, f.x, "%.3f");
  os << ',';
  put(os, f.y, "%.3f");
  os << ',';
  put(os, f.yaw);
  os << ',';
  put(os, f.v, "%.3f");
  os << ',';
  put(os, f.a, "%.3f");
  os << ',';
  put(os, f.steer, "%.5f");
  os << ',';
  put(os, f.steer_cmd, "%.5f");
  os << ',';
  put(os, f.accel_cmd, "%.3f");
  os << ',';
  put(os, f.s, "%.2f");
  os << ',';
  put(os, f.cte, "%.4f");
  os << ',';
  put(os, f.heading_err);
  os << ',';
  put(os, f.v_ref, "%.3f");
  os << ',';
  put(os, f.target_speed, "%.3f");
  os << ',' << f.lead_id << ',';
  put(os, f.lead_gap, "%.2f");
  os << ',';
  put(os, f.gt_gap, "%.2f");
  os << ',';
  put(os, f.ttc, "%.3f");
  os << ',';
  put(os, f.planner_latency_ms, "%.2f");
  os << ',' << f.deadline_miss << ',' << f.n_tracks << ',' << f.n_relevant << ',' << f.n_missed << ','
     << f.n_phantom << ',' << f.engaged << '\n';
}

nlohmann::json summary_to_json(const DriveSummary& s) {
  return {
      {"scenario_id", s.scenario_id},
      {"family", s.family},
      {"seed", s.seed},
      {"build", s.build},
      {"weather", s.weather},
      {"outcome", s.outcome},
      {"reason", s.reason},
      {"duration_s", s.duration_s},
      {"distance_m", s.distance_m},
      {"route_completion", s.route_completion},
      {"mean_speed", s.mean_speed},
      {"cte_max", s.cte_max},
      {"cte_rms", s.cte_rms},
      {"cte_p95", s.cte_p95},
      {"heading_err_max", s.heading_err_max},
      {"jerk_rms", s.jerk_rms},
      {"accel_min", s.accel_min},
      {"lat_acc_max", s.lat_acc_max},
      {"steer_reversal_rate", s.steer_reversal_rate},
      {"accel_reversal_rate", s.accel_reversal_rate},
      {"min_ttc", finite_or_null(s.min_ttc)},
      {"min_gap", finite_or_null(s.min_gap)},
      {"planner_p50_ms", s.planner_p50_ms},
      {"planner_p99_ms", s.planner_p99_ms},
      {"planner_max_ms", s.planner_max_ms},
      {"planner_cycles", s.planner_cycles},
      {"deadline_misses", s.deadline_misses},
      {"det_tp", s.det_tp},
      {"det_fn", s.det_fn},
      {"det_fp", s.det_fp},
      {"recall", s.recall},
      {"precision", s.precision},
      {"hard_brakes", s.hard_brakes},
      {"n_events", s.n_events},
  };
}

nlohmann::json event_to_json(const Event& e) {
  return {{"t", e.t},
          {"kind", e.kind},
          {"severity", e.severity},
          {"value", finite_or_null(e.value)},
          {"duration", e.duration},
          {"detail", e.detail}};
}

}  // namespace fg
