#pragma once

#include "fleetguard/path.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

struct ControllerParams {
  double lookahead_gain = 0.55;     // s; lookahead distance grows with speed
  double lookahead_min = 6.0;       // m
  double steer_gain = 1.0;          // multiplier on the pure-pursuit steering angle
  double speed_kp = 0.8;            // 1/s
  double speed_ki = 0.08;           // 1/s^2
  double integral_limit = 2.0;      // m/s, anti-windup clamp on the speed error integral
  double jerk_limit = 12.0;         // m/s^3, slew limit on the acceleration command
  double actuator_delay_ms = 40.0;  // control stack + CAN latency before actuation
};

// What planning hands to control every tick.
struct ControlTarget {
  const Path* path = nullptr;  // lane centre line to track
  double lateral_offset = 0.0;  // m, left positive, applied on top of the path
  double accel = 0.0;           // feed-forward acceleration
  double v_ref = 0.0;           // speed reference
};

struct ControlOutput {
  double steer_cmd = 0.0;
  double accel_cmd = 0.0;
  double lookahead = 0.0;
  Vec2 target;
};

// Pure pursuit on the rear axle for steering, PI on speed with a feed-forward term.
class Controller {
 public:
  Controller(const ControllerParams& cp, const VehicleParams& vp, double dt);

  ControlOutput update(const VehicleState& s, const ControlTarget& tgt);
  void reset_integral() { integral_ = 0.0; }

 private:
  ControllerParams cp_;
  VehicleParams vp_;
  double dt_;
  double integral_ = 0.0;
  double last_accel_cmd_ = 0.0;
  const Path* last_path_ = nullptr;
  size_t hint_ = Path::npos;
};

}  // namespace fg
