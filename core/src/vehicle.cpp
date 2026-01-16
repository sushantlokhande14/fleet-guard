#include "fleetguard/vehicle.hpp"

#include <cmath>

namespace fg {

namespace {

struct Deriv {
  double dx, dy, dyaw;
};

Deriv deriv(double yaw, double v, double steer, double wheelbase) {
  // slip angle at the centre with the CG at mid-wheelbase
  const double beta = std::atan(0.5 * std::tan(steer));
  return {v * std::cos(yaw + beta), v * std::sin(yaw + beta), v / wheelbase * std::cos(beta) * std::tan(steer)};
}

}  // namespace

void step_vehicle(VehicleState& s, const VehicleParams& p, double dt) {
  const double v0 = s.v;
  const double v1 = std::max(0.0, v0 + s.a * dt);
  const double vm = 0.5 * (v0 + v1);

  const Deriv k1 = deriv(s.yaw, v0, s.steer, p.wheelbase);
  const double yaw_mid = s.yaw + 0.5 * dt * k1.dyaw;
  const Deriv k2 = deriv(yaw_mid, vm, s.steer, p.wheelbase);

  s.pos.x += dt * k2.dx;
  s.pos.y += dt * k2.dy;
  s.yaw = wrap_angle(s.yaw + dt * k2.dyaw);
  s.v = v1;
  if (s.v <= 0.0 && s.a < 0.0) s.a = 0.0;  // parked, brakes hold
}

Actuators::Actuators(const VehicleParams& vp, double delay_s, double dt, double friction)
    : vp_(vp), dt_(dt), friction_(friction) {
  delay_ticks_ = static_cast<size_t>(std::lround(std::max(0.0, delay_s) / dt));
}

void Actuators::apply(double steer_cmd, double accel_cmd, VehicleState& s) {
  queue_.push_back({steer_cmd, accel_cmd});
  // until the pipeline fills, the actuators hold their initial command (zero)
  if (queue_.size() <= delay_ticks_) return;
  const Cmd c = queue_.front();
  queue_.pop_front();

  const double steer_target = clamp(c.steer, -vp_.max_steer, vp_.max_steer);
  double dsteer = (steer_target - s.steer) * (1.0 - std::exp(-dt_ / vp_.steer_tau));
  const double max_d = vp_.steer_rate * dt_;
  dsteer = clamp(dsteer, -max_d, max_d);
  s.steer += dsteer;

  // tyres cannot deliver more than mu*g, braking or driving
  const double grip = friction_ * kGravity;
  const double accel_target = clamp(c.accel, -std::min(vp_.max_decel, grip), std::min(vp_.max_accel, grip));
  s.a += (accel_target - s.a) * (1.0 - std::exp(-dt_ / vp_.accel_tau));
}

}  // namespace fg
