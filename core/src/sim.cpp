#include "fleetguard/sim.hpp"

#include <algorithm>
#include <cmath>

#include "fleetguard/actors.hpp"
#include "fleetguard/controller.hpp"
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

namespace {

// Counts direction reversals of a signal, ignoring wiggles smaller than `gap`
// (the steering-reversal-rate metric from driver behaviour studies).
class ReversalCounter {
 public:
  explicit ReversalCounter(double gap) : gap_(gap) {}
  void add(double x) {
    if (!init_) {
      lo_ = hi_ = x;
      init_ = true;
      return;
    }
    if (dir_ >= 0) {
      if (x > hi_) hi_ = x;
      if (hi_ - x > gap_) {
        if (dir_ > 0) ++count_;
        dir_ = -1;
        lo_ = x;
      }
    }
    if (dir_ <= 0) {
      if (x < lo_) lo_ = x;
      if (x - lo_ > gap_) {
        if (dir_ < 0) ++count_;
        dir_ = 1;
        hi_ = x;
      }
    }
  }
  int count() const { return count_; }

 private:
  double gap_;
  bool init_ = false;
  int dir_ = 0;
  double lo_ = 0, hi_ = 0;
  int count_ = 0;
};

}  // namespace

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
  Planner planner(build.planner, sc);
  Controller controller(build.control, vp, dt);
  Actuators actuators(vp, build.control.actuator_delay_ms / 1000.0, dt, sc.friction);

  std::vector<double> cte_abs;
  double cte_sq = 0.0, jerk_sq = 0.0, speed_sum = 0.0;
  ReversalCounter steer_rev(0.01), accel_rev(0.5);
  size_t hint = Path::npos;
  double prev_a = ego.a;
  long tick = 0;
  double t = 0.0;
  double last_s = 0.0;

  while (true) {
    const Projection pr = sc.route.project(ego.pos, hint);
    hint = pr.segment;
    last_s = pr.s;

    const Hazard hz = nearest_in_path(ego, vp, actors.states());
    sum.min_gap = std::min(sum.min_gap, hz.gap);
    sum.min_ttc = std::min(sum.min_ttc, hz.ttc);

    const Plan& plan = planner.update(t, ego);
    ControlTarget tgt{&planner.active_path(), plan.lateral_offset, plan.accel, plan.v_ref(t)};
    const ControlOutput cmd = controller.update(ego, tgt);

    if (opt.record_frames && tick % opt.log_every == 0) {
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
      f.gt_gap = hz.gap;
      f.ttc = hz.ttc;
      res.frames.push_back(f);
    }

    // per-tick statistics
    const double cte = std::fabs(pr.lateral);
    cte_abs.push_back(cte);
    cte_sq += cte * cte;
    sum.heading_err_max = std::max(sum.heading_err_max, std::fabs(wrap_angle(ego.yaw - pr.heading)));
    speed_sum += ego.v;
    steer_rev.add(ego.steer);
    accel_rev.add(ego.a);

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
  sum.n_events = static_cast<int>(res.events.size());
  return res;
}

}  // namespace fg
