#include "fleetguard/planner.hpp"

#include <cmath>

namespace fg {

Planner::Planner(const PlannerParams& p, const Scenario& sc)
    : p_(p), sc_(sc), rng_(derive_seed(sc.seed, stream::kPlanner)) {}

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

// Intelligent Driver Model interaction term towards an object `gap` metres ahead.
double Planner::interaction_accel(double v, double gap, double v_obj) const {
  const double dv = v - v_obj;
  const double s_star = p_.min_gap_m + std::max(0.0, v * p_.headway_s + v * dv / (2.0 * std::sqrt(p_.max_accel * p_.comfort_decel)));
  const double ratio = s_star / std::max(gap, 0.1);
  return p_.max_accel * (1.0 - ratio * ratio);
}

Plan Planner::compute(double t, const VehicleState& ego, const std::vector<PerceivedObject>& objects) {
  const Path& path = active_path();
  const Projection pr = path.project(ego.pos, hint_);
  hint_ = pr.segment;

  Plan plan;
  plan.t_plan = t;
  plan.v0 = ego.v;
  plan.use_map = !p_.use_live_lane;
  plan.v_cap = free_road_target(pr.s, ego.v);
  double accel = clamp(p_.speed_gain * (plan.v_cap - ego.v), -p_.comfort_decel, p_.max_accel);

  plan.lateral_offset = p_.lateral_bias_m;
  const double k_ahead = path.curvature_at(pr.s + 10.0);
  if (p_.curve_offset_m != 0.0 && std::fabs(k_ahead) > p_.curve_offset_kappa) {
    // pushes the car towards the outside of the bend
    plan.lateral_offset -= sign(k_ahead) * p_.curve_offset_m;
  }

  // --- react to objects in (or about to enter) our corridor ------------------
  std::unordered_map<int, size_t> hints;
  for (const auto& o : objects) {
    auto h = track_hints_.find(o.track_id);
    const Projection op = h != track_hints_.end() ? path.project(o.pos, h->second, 12) : path.project(o.pos, pr.segment, 160);
    hints[o.track_id] = op.segment;
    const double ds = op.s - pr.s;
    if (ds < -2.0 || ds > 120.0) continue;
    const Vec2 tangent = Vec2::from_angle(op.heading);
    const double v_along = o.vel.dot(tangent);
    const double lat = op.lateral - plan.lateral_offset;
    const double lat_rate = o.vel.dot(tangent.perp());
    const double corridor = 0.5 * vp_.width + 0.5 * o.width + p_.lateral_margin_m;

    bool in_path = std::fabs(lat) < corridor;
    if (!in_path && o.kind == ActorKind::Vehicle && p_.predict_cut_ins && lat * lat_rate < 0.0) {
      // closing laterally: will it be in our lane within the horizon?
      in_path = std::fabs(lat + lat_rate * p_.cut_in_horizon_s) < corridor;
    }
    if (!in_path && o.kind == ActorKind::Pedestrian && p_.yield_to_crossing_peds && lat * lat_rate < 0.0) {
      const double t_enter = (std::fabs(lat) - corridor - 0.5) / std::max(std::fabs(lat_rate), 1e-3);
      in_path = t_enter < p_.ped_horizon_s;
    }
    if (!in_path) continue;

    const double gap = ds - 0.5 * (vp_.length + o.length);
    const double v_obj = o.kind == ActorKind::Pedestrian ? 0.0 : std::max(0.0, v_along);
    const double a_obj = interaction_accel(ego.v, gap, v_obj);
    if (a_obj < accel) {
      accel = a_obj;
      plan.lead_id = o.track_id;
      plan.lead_gap = gap;
    } else if (plan.lead_id < 0) {
      plan.lead_id = o.track_id;  // nearest in-path object, for telemetry
      plan.lead_gap = gap;
    }
  }
  track_hints_.swap(hints);
  plan.accel = clamp(accel, -p_.max_decel, p_.max_accel);
  return plan;
}

const Plan& Planner::update(double t, const VehicleState& ego, const std::vector<PerceivedObject>& objects,
                            std::vector<Event>& events) {
  if (!started_) {
    // the stack was already running when the scenario starts
    current_ = compute(t, ego, objects);
    started_ = true;
  }
  if (has_pending_ && t + 1e-9 >= pending_ready_) {
    current_ = pending_;
    has_pending_ = false;
  }
  if (t + 1e-9 >= next_cycle_) {
    next_cycle_ += p_.cycle_ms / 1000.0;
    // fixed draw order per cycle so builds share their luck
    const double n = rng_.normal();
    const double u_spike = rng_.uniform();
    const double u_mag = rng_.uniform();
    double latency = p_.latency_mean_ms + p_.latency_jitter_ms * n + p_.latency_per_object_ms * objects.size();
    if (u_spike < p_.spike_prob) latency += p_.spike_ms * lerp(0.6, 1.4, u_mag);
    latency = std::max(5.0, latency);

    stats_.cycles++;
    stats_.latencies_ms.push_back(latency);
    stats_.last_latency_ms = latency;
    const bool missed = latency > p_.cycle_ms;
    stats_.last_missed = missed;
    if (latency > 0.8 * p_.cycle_ms) {
      events.push_back({t, "latency_spike", missed ? 2 : 1, latency, latency / 1000.0, missed ? "deadline_miss" : "near_budget"});
    }
    if (missed) {
      stats_.deadline_misses++;
      stats_.consecutive_misses++;
    } else {
      stats_.consecutive_misses = 0;
      pending_ = compute(t, ego, objects);
      pending_ready_ = t + latency / 1000.0;
      has_pending_ = true;
    }
  }
  return current_;
}

}  // namespace fg
