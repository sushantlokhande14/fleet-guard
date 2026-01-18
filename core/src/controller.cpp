#include "fleetguard/controller.hpp"

#include <cmath>

namespace fg {

Controller::Controller(const ControllerParams& cp, const VehicleParams& vp, double dt) : cp_(cp), vp_(vp), dt_(dt) {}

ControlOutput Controller::update(const VehicleState& s, const ControlTarget& tgt) {
  ControlOutput out;
  const Vec2 fwd = Vec2::from_angle(s.yaw);
  const Vec2 rear = s.pos - fwd * (0.5 * vp_.wheelbase);

  // --- lateral: pure pursuit -------------------------------------------------
  if (tgt.path != last_path_) {
    hint_ = Path::npos;  // switched path (map vs live lane): full search once
    last_path_ = tgt.path;
  }
  const Projection pr = tgt.path->project(rear, hint_);
  hint_ = pr.segment;
  const double ld = std::max(cp_.lookahead_min, cp_.lookahead_gain * s.v);
  const double st = pr.s + ld;
  out.target = tgt.path->point_at(st) + tgt.path->normal_at(st) * tgt.lateral_offset;
  out.lookahead = ld;

  const Vec2 to_target = out.target - rear;
  const double alpha = wrap_angle(to_target.angle() - s.yaw);
  const double dist = std::max(1.0, to_target.norm());
  const double delta = std::atan2(2.0 * vp_.wheelbase * std::sin(alpha), dist);
  out.steer_cmd = clamp(cp_.steer_gain * delta, -vp_.max_steer, vp_.max_steer);

  // --- longitudinal: feed-forward + PI on speed ------------------------------
  const double err = tgt.v_ref - s.v;
  integral_ = clamp(integral_ + err * dt_, -cp_.integral_limit, cp_.integral_limit);
  double a = tgt.accel + cp_.speed_kp * err + cp_.speed_ki * integral_;
  a = clamp(a, -vp_.max_decel, vp_.max_accel);
  const double max_da = cp_.jerk_limit * dt_;
  a = clamp(a, last_accel_cmd_ - max_da, last_accel_cmd_ + max_da);
  // stopped and asked to hold: do not wind up a reverse command
  if (s.v < 0.05 && tgt.v_ref < 0.05) {
    a = std::min(a, 0.0);
    integral_ = 0.0;
  }
  last_accel_cmd_ = a;
  out.accel_cmd = a;
  return out;
}

}  // namespace fg
