#pragma once

#include <deque>

#include "fleetguard/math.hpp"

namespace fg {

struct VehicleParams {
  double wheelbase = 2.8;   // m
  double length = 4.7;      // m
  double width = 1.9;       // m
  double max_steer = 0.55;  // rad at the road wheel
  double max_accel = 3.5;   // m/s^2, powertrain limit
  double max_decel = 9.0;   // m/s^2, brake limit before friction
  double steer_tau = 0.12;  // s, steering actuator time constant
  double steer_rate = 0.7;  // rad/s, steering actuator slew limit
  double accel_tau = 0.25;  // s, longitudinal actuator time constant
};

// Reference point is the vehicle centre; dynamics are a kinematic bicycle with
// the slip angle at the centre of gravity (mid-wheelbase).
struct VehicleState {
  Vec2 pos;
  double yaw = 0.0;
  double v = 0.0;
  double a = 0.0;      // actual longitudinal acceleration
  double steer = 0.0;  // actual road-wheel angle
};

// Advance the kinematic bicycle one step with midpoint integration.
void step_vehicle(VehicleState& s, const VehicleParams& p, double dt);

// Actuators between the controller and the vehicle: a pure transport delay
// (control stack + bus latency), then first-order lag, slew limit and friction cap.
class Actuators {
 public:
  Actuators(const VehicleParams& vp, double delay_s, double dt, double friction);

  // Feed commands for this tick, writes the realised steer/accel into the state.
  void apply(double steer_cmd, double accel_cmd, VehicleState& s);

 private:
  struct Cmd {
    double steer, accel;
  };
  const VehicleParams vp_;
  double dt_;
  double friction_;
  size_t delay_ticks_;
  std::deque<Cmd> queue_;
};

}  // namespace fg
