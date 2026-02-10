#include "fleetguard/compare.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

#include "fleetguard/math.hpp"

namespace fg {

namespace {

// Frames reduced to a strictly increasing function of s.
struct Track {
  std::vector<double> s, t, lat, v;
};

Track monotone(const std::vector<Frame>& frames) {
  Track tr;
  for (const auto& f : frames) {
    if (!tr.s.empty() && f.s <= tr.s.back()) continue;  // stopped or rolled back
    tr.s.push_back(f.s);
    tr.t.push_back(f.t);
    tr.lat.push_back(f.cte);
    tr.v.push_back(f.v);
  }
  return tr;
}

double interp(const std::vector<double>& xs, const std::vector<double>& ys, double x) {
  auto it = std::upper_bound(xs.begin(), xs.end(), x);
  if (it == xs.begin()) return ys.front();
  if (it == xs.end()) return ys.back();
  const size_t i = static_cast<size_t>(std::distance(xs.begin(), it));
  const double u = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return lerp(ys[i - 1], ys[i], u);
}

double cap_ttc(double t) { return std::isfinite(t) ? std::min(t, 10.0) : 10.0; }

}  // namespace

PairMetrics compare_drives(const DriveResult& base, const DriveResult& cand, const CompareOptions& opt) {
  PairMetrics p;
  const DriveSummary& b = base.summary;
  const DriveSummary& c = cand.summary;
  p.scenario_id = c.scenario_id;
  p.baseline = b.build;
  p.candidate = c.build;
  p.outcome_changed = b.outcome != c.outcome;

  p.d_cte_max = c.cte_max - b.cte_max;
  p.d_jerk_rms = c.jerk_rms - b.jerk_rms;
  p.d_steer_reversal_rate = c.steer_reversal_rate - b.steer_reversal_rate;
  p.d_accel_reversal_rate = c.accel_reversal_rate - b.accel_reversal_rate;
  p.d_min_ttc = cap_ttc(c.min_ttc) - cap_ttc(b.min_ttc);
  p.d_planner_p99_ms = c.planner_p99_ms - b.planner_p99_ms;
  p.d_recall = c.recall - b.recall;
  p.d_precision = c.precision - b.precision;
  p.d_deadline_misses = c.deadline_misses - b.deadline_misses;
  p.d_hard_brakes = c.hard_brakes - b.hard_brakes;

  const Track tb = monotone(base.frames);
  const Track tc = monotone(cand.frames);
  if (tb.s.size() < 2 || tc.s.size() < 2) return p;

  const double s0 = std::max(tb.s.front(), tc.s.front());
  const double s1 = std::min(tb.s.back(), tc.s.back());
  if (s1 <= s0) return p;
  p.common_s = s1 - s0;

  double sum_lat = 0.0, sum_v2 = 0.0;
  int n = 0;
  for (double s = s0; s <= s1 + 1e-9; s += opt.ds) {
    const double dlat = std::fabs(interp(tc.s, tc.lat, s) - interp(tb.s, tb.lat, s));
    const double dv = interp(tc.s, tc.v, s) - interp(tb.s, tb.v, s);
    sum_lat += dlat;
    sum_v2 += dv * dv;
    p.lat_max_abs_diff = std::max(p.lat_max_abs_diff, dlat);
    if (p.first_divergence_s < 0.0 && (dlat > opt.diverge_lat || std::fabs(dv) > opt.diverge_speed)) {
      p.first_divergence_s = s;
      p.first_divergence_t = interp(tc.s, tc.t, s);
    }
    ++n;
  }
  p.lat_mean_abs_diff = sum_lat / n;
  p.speed_rmse = std::sqrt(sum_v2 / n);
  p.time_delta_s = interp(tc.s, tc.t, s1) - interp(tb.s, tb.t, s1);
  return p;
}

nlohmann::json pair_to_json(const PairMetrics& p) {
  return {
      {"scenario_id", p.scenario_id},
      {"baseline", p.baseline},
      {"candidate", p.candidate},
      {"common_s", p.common_s},
      {"lat_mean_abs_diff", p.lat_mean_abs_diff},
      {"lat_max_abs_diff", p.lat_max_abs_diff},
      {"speed_rmse", p.speed_rmse},
      {"time_delta_s", p.time_delta_s},
      {"first_divergence_s", p.first_divergence_s < 0 ? nlohmann::json(nullptr) : nlohmann::json(p.first_divergence_s)},
      {"first_divergence_t", p.first_divergence_t < 0 ? nlohmann::json(nullptr) : nlohmann::json(p.first_divergence_t)},
      {"outcome_changed", p.outcome_changed},
      {"d_cte_max", p.d_cte_max},
      {"d_jerk_rms", p.d_jerk_rms},
      {"d_steer_reversal_rate", p.d_steer_reversal_rate},
      {"d_accel_reversal_rate", p.d_accel_reversal_rate},
      {"d_min_ttc", p.d_min_ttc},
      {"d_planner_p99_ms", p.d_planner_p99_ms},
      {"d_recall", p.d_recall},
      {"d_precision", p.d_precision},
      {"d_deadline_misses", p.d_deadline_misses},
      {"d_hard_brakes", p.d_hard_brakes},
  };
}

}  // namespace fg
