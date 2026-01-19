#include "fleetguard/planner.hpp"

#include <cmath>

namespace fg {

Planner::Planner(const PlannerParams& p, const Scenario& sc) : p_(p), sc_(sc) {}

double Planner::free_road_target(double s, double v) const {
  // highest speed from which we can still slow to every upcoming limit
  // (posted limit or curvature limit) at comfortable deceleration
  const double horizon = v * v / (2.0 * p_.comfort_decel) + 30.0;
  const Path& path = active_path();
  double target = kInf;
  for (double ds = 0.0; ds <= horizon; ds += 2.0) {
    const double si = s + ds;
    double lim = sc_.speed_limit_at(si);
    const double k = std::fabs(path.curvature_at(si));
    if (k > 1e-4) lim = std::min(lim, std::sqrt(p_.lat_accel_max / k));
    const double reachable = std::sqrt(lim * lim + 2.0 * p_.comfort_decel * std::max(0.0, ds - 0.5 * v));
    target = std::min(target, reachable);
  }
  return target;
}

Plan Planner::compute(double t, const VehicleState& ego) {
  const Path& path = active_path();
  const Projection pr = path.project(ego.pos, hint_);
  hint_ = pr.segment;

  Plan plan;
  plan.t_plan = t;
  plan.v0 = ego.v;
  plan.use_map = !p_.use_live_lane;
  plan.v_cap = free_road_target(pr.s, ego.v);
  plan.accel = clamp(p_.speed_gain * (plan.v_cap - ego.v), -p_.comfort_decel, p_.max_accel);

  plan.lateral_offset = p_.lateral_bias_m;
  const double k_ahead = path.curvature_at(pr.s + 10.0);
  if (p_.curve_offset_m != 0.0 && std::fabs(k_ahead) > p_.curve_offset_kappa) {
    // pushes the car towards the outside of the bend
    plan.lateral_offset -= sign(k_ahead) * p_.curve_offset_m;
  }
  return plan;
}

const Plan& Planner::update(double t, const VehicleState& ego) {
  if (t + 1e-9 >= next_cycle_) {
    current_ = compute(t, ego);
    next_cycle_ += p_.cycle_ms / 1000.0;
  }
  return current_;
}

}  // namespace fg
