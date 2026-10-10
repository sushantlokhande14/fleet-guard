#include "fleetguard/sim.hpp"

#include <algorithm>
#include <cmath>

#include "fleetguard/actors.hpp"
#include "fleetguard/controller.hpp"
#include "fleetguard/events.hpp"
#include "fleetguard/perception.hpp"
#include "fleetguard/planner.hpp"
#include "fleetguard/safety.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

double percentile(std::vector<double> v, double p) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  const double idx = clamp(p, 0.0, 1.0) * (v.size() - 1);
  const size_t lo = static_cast<size_t>(std::floor(idx));
  const size_t hi = std::min(lo + 1, v.size() - 1);
  return lerp(v[lo], v[hi], idx - lo);
}

DriveResult run_drive(const Scenario& sc, const BuildConfig& build, const SimOptions& opt) {
  DriveResult res;
  DriveSummary& sum = res.summary;
  sum.scenario_id = sc.id();
  sum.family = sc.family;
  sum.seed = sc.seed;
  sum.build = build.name;
  sum.weather = to_string(sc.weather);

  const double dt = opt.dt;
  VehicleParams vp;
  VehicleState ego;
  ego.pos = sc.route.point_at(0.0);
  ego.yaw = sc.route.heading_at(0.0);
  ego.v = sc.ego_v0;

  ActorSim actors(sc);
  Perception perception(build.perception, sc, dt);
  Planner planner(build.planner, sc);
  Controller controller(build.control, vp, dt);
  Actuators actuators(vp, build.control.actuator_delay_ms / 1000.0, dt, sc.friction);

  // event detectors (thresholds are fixed so every build is judged the same way)
  EpisodeDetector off_route("off_route", 2, 0.5);
  EpisodeDetector hard_brake("hard_brake", 2, 0.2, /*peak_is_max=*/false);
  EpisodeDetector steer_osc("steer_oscillation", 2, 0.5);
  EpisodeDetector accel_osc("accel_oscillation", 2, 0.5);
  OscillationDetector steer_osc_sig(0.01, 4.0, 4);
  // >= 0.6 Hz: curve-to-curve speed changes on winding roads are slower than that
  OscillationDetector accel_osc_sig(0.6, 4.0, 5);
  ReversalCounter steer_rev(0.01), accel_rev(0.5);

  std::vector<double> cte_abs;
  double cte_sq = 0.0, jerk_sq = 0.0, speed_sum = 0.0;
  size_t hint = Path::npos;
  double prev_a = ego.a;
  long tick = 0;
  double t = 0.0;
  double last_s = 0.0;
  Frame last_frame;

  auto disengage = [&](const std::string& reason, double value, const std::string& detail) {
    sum.outcome = "disengaged";
    sum.reason = reason;
    res.events.push_back({t, "disengagement", 3, value, 0.0, reason + (detail.empty() ? "" : " " + detail)});
  };

  while (true) {
    const Projection pr = sc.route.project(ego.pos, hint);
    hint = pr.segment;
    last_s = pr.s;

    const Hazard hz = nearest_in_path(sc.route, pr, ego, vp, actors.states());
    sum.min_gap = std::min(sum.min_gap, hz.gap);
    sum.min_ttc = std::min(sum.min_ttc, hz.ttc);

    const auto& objects = perception.update(t, ego, actors.states(), res.events);
    const PerceptionTickStats& ps = perception.tick_stats();
    const Plan& plan = planner.update(t, ego, objects, res.events);
    const PlannerStats& pst = planner.stats();
    ControlTarget tgt{&planner.active_path(), plan.lateral_offset, plan.accel, plan.v_ref(t)};
    const ControlOutput cmd = controller.update(ego, tgt);

    Frame f;
    f.t = t;
    f.x = ego.pos.x;
    f.y = ego.pos.y;
    f.yaw = ego.yaw;
    f.v = ego.v;
    f.a = ego.a;
    f.steer = ego.steer;
    f.steer_cmd = cmd.steer_cmd;
    f.accel_cmd = cmd.accel_cmd;
    f.s = pr.s;
    f.cte = pr.lateral;
    f.heading_err = wrap_angle(ego.yaw - pr.heading);
    f.v_ref = tgt.v_ref;
    f.target_speed = plan.v_cap;
    f.lead_id = plan.lead_id;
    f.lead_gap = plan.lead_gap;
    f.gt_gap = hz.gap;
    f.ttc = hz.ttc;
    f.planner_latency_ms = pst.last_latency_ms;
    f.deadline_miss = pst.last_missed ? 1 : 0;
    f.n_tracks = static_cast<int>(objects.size());
    f.n_relevant = ps.relevant;
    f.n_missed = ps.missed;
    f.n_phantom = ps.phantom;
    if (opt.record_frames && tick % opt.log_every == 0) res.frames.push_back(f);
    last_frame = f;

    // per-tick statistics and event detection
    const double cte = std::fabs(pr.lateral);
    cte_abs.push_back(cte);
    cte_sq += cte * cte;
    sum.heading_err_max = std::max(sum.heading_err_max, std::fabs(f.heading_err));
    speed_sum += ego.v;
    steer_rev.add(ego.steer);
    accel_rev.add(ego.a);
    off_route.update(t, cte > 0.5, cte, res.events);
    hard_brake.update(t, ego.a < -4.0, ego.a, res.events);
    steer_osc.update(t, steer_osc_sig.update(t, ego.steer), steer_osc_sig.in_window(), res.events);
    accel_osc.update(t, accel_osc_sig.update(t, ego.a), accel_osc_sig.in_window(), res.events);

    // safety monitor: the safety driver takes over on imminent conflict or lane departure
    if (hz.ttc < opt.ttc_takeover && hz.gap < opt.takeover_gap_max) {
      disengage("ttc_takeover", hz.ttc, std::string(to_string(hz.kind)) + " " + std::to_string(hz.id));
      break;
    }
    if (pst.consecutive_misses >= build.planner.watchdog_misses) {
      disengage("planner_watchdog", pst.consecutive_misses, "");
      break;
    }
    if (cte > opt.lane_departure_m) {
      disengage("lane_departure", cte, "");
      break;
    }

    // advance the world
    actuators.apply(cmd.steer_cmd, cmd.accel_cmd, ego);
    step_vehicle(ego, vp, dt);
    actors.step(t, dt);
    t += dt;
    ++tick;

    const double jerk = (ego.a - prev_a) / dt;
    prev_a = ego.a;
    jerk_sq += jerk * jerk;
    sum.accel_min = std::min(sum.accel_min, ego.a);
    sum.lat_acc_max = std::max(sum.lat_acc_max, std::fabs(ego.v * ego.v * std::tan(ego.steer) / vp.wheelbase));
    sum.distance_m += ego.v * dt;

    bool crashed = false;
    for (const auto& a : actors.states()) {
      if (collides(ego, vp, a)) {
        sum.outcome = "collision";
        sum.reason = to_string(a.kind);
        res.events.push_back({t, "collision", 3, ego.v, 0.0, std::string(to_string(a.kind)) + " " + std::to_string(a.id)});
        crashed = true;
        break;
      }
    }
    if (crashed) break;
    if (pr.s >= sc.route.length() - 2.0) break;
    if (t >= sc.time_limit) {
      sum.outcome = "timeout";
      sum.reason = "time_limit";
      break;
    }
  }

  // close open episodes and stamp the final state so replays show where it ended
  perception.flush(t, res.events);
  off_route.flush(t, res.events);
  hard_brake.flush(t, res.events);
  steer_osc.flush(t, res.events);
  accel_osc.flush(t, res.events);
  if (opt.record_frames && sum.outcome != "completed") {
    last_frame.engaged = 0;
    if (res.frames.empty() || res.frames.back().t < last_frame.t) res.frames.push_back(last_frame);
    else res.frames.back().engaged = 0;
  }
  std::stable_sort(res.events.begin(), res.events.end(), [](const Event& a, const Event& b) { return a.t < b.t; });

  const double n = static_cast<double>(std::max<long>(1, tick));
  sum.duration_s = t;
  sum.route_completion = clamp(last_s / sc.route.length(), 0.0, 1.0);
  if (sum.outcome == "completed") sum.route_completion = 1.0;
  sum.mean_speed = speed_sum / n;
  sum.cte_max = cte_abs.empty() ? 0.0 : *std::max_element(cte_abs.begin(), cte_abs.end());
  sum.cte_rms = std::sqrt(cte_sq / n);
  sum.cte_p95 = percentile(cte_abs, 0.95);
  sum.jerk_rms = std::sqrt(jerk_sq / n);
  sum.steer_reversal_rate = steer_rev.count() / std::max(t, 1.0);
  sum.accel_reversal_rate = accel_rev.count() / std::max(t, 1.0);
  sum.hard_brakes = hard_brake.episodes();
  const PlannerStats& pst = planner.stats();
  sum.planner_cycles = pst.cycles;
  sum.deadline_misses = pst.deadline_misses;
  sum.planner_p50_ms = percentile(pst.latencies_ms, 0.50);
  sum.planner_p99_ms = percentile(pst.latencies_ms, 0.99);
  sum.planner_max_ms = pst.latencies_ms.empty() ? 0.0 : *std::max_element(pst.latencies_ms.begin(), pst.latencies_ms.end());
  sum.det_tp = perception.total_tp();
  sum.det_fn = perception.total_fn();
  sum.det_fp = perception.total_fp();
  sum.recall = sum.det_tp + sum.det_fn > 0 ? static_cast<double>(sum.det_tp) / (sum.det_tp + sum.det_fn) : 1.0;
  sum.precision = sum.det_tp + sum.det_fp > 0 ? static_cast<double>(sum.det_tp) / (sum.det_tp + sum.det_fp) : 1.0;
  sum.n_events = static_cast<int>(res.events.size());
  return res;
}

}  // namespace fg
