#include <gtest/gtest.h>

#include <cmath>

#include "fleetguard/vehicle.hpp"

using namespace fg;

TEST(Vehicle, StraightLineAcceleration) {
  VehicleParams p;
  VehicleState s;
  s.a = 2.0;
  const double dt = 0.01;
  for (int i = 0; i < 500; ++i) step_vehicle(s, p, dt);  // 5 s
  EXPECT_NEAR(s.v, 10.0, 1e-9);
  EXPECT_NEAR(s.pos.x, 25.0, 1e-6);  // 0.5 a t^2
  EXPECT_NEAR(s.pos.y, 0.0, 1e-12);
}

TEST(Vehicle, NeverRollsBackwards) {
  VehicleParams p;
  VehicleState s;
  s.v = 1.0;
  s.a = -5.0;
  for (int i = 0; i < 100; ++i) step_vehicle(s, p, 0.05);
  EXPECT_DOUBLE_EQ(s.v, 0.0);
  EXPECT_GT(s.pos.x, 0.0);
  EXPECT_LT(s.pos.x, 0.2);
}

TEST(Vehicle, ConstantSteerTracesCircle) {
  VehicleParams p;
  VehicleState s;
  s.v = 8.0;
  s.steer = 0.2;
  const double beta = std::atan(0.5 * std::tan(s.steer));
  const double R = p.wheelbase / (std::cos(beta) * std::tan(s.steer));
  const double dt = 0.005;
  const double period = 2 * kPi * R / s.v;
  Vec2 start = s.pos;
  double max_r_err = 0;
  // centre of the circle traced by the reference point
  const Vec2 centre = start + Vec2::from_angle(s.yaw + beta).perp() * R;
  for (double t = 0; t < period; t += dt) {
    step_vehicle(s, p, dt);
    max_r_err = std::max(max_r_err, std::fabs((s.pos - centre).norm() - R));
  }
  EXPECT_LT(max_r_err, 0.01);
  EXPECT_LT(distance(s.pos, start), 0.2);
}

TEST(Actuators, DelayHoldsCommand) {
  VehicleParams vp;
  VehicleState s;
  const double dt = 0.05;
  Actuators act(vp, 0.10, dt, 1.0);  // two ticks of delay
  act.apply(0.0, 2.0, s);
  EXPECT_DOUBLE_EQ(s.a, 0.0);
  act.apply(0.0, 2.0, s);
  EXPECT_DOUBLE_EQ(s.a, 0.0);
  act.apply(0.0, 2.0, s);
  EXPECT_GT(s.a, 0.0);
}

TEST(Actuators, LagConvergesAndRespectsSlew) {
  VehicleParams vp;
  VehicleState s;
  const double dt = 0.05;
  Actuators act(vp, 0.0, dt, 1.0);
  act.apply(0.5, 0.0, s);
  EXPECT_LE(s.steer, vp.steer_rate * dt + 1e-12);
  for (int i = 0; i < 200; ++i) act.apply(0.3, 1.0, s);
  EXPECT_NEAR(s.steer, 0.3, 1e-3);
  EXPECT_NEAR(s.a, 1.0, 1e-3);
}

TEST(Actuators, FrictionCapsBraking) {
  VehicleParams vp;
  VehicleState s;
  Actuators wet(vp, 0.0, 0.05, 0.5);
  for (int i = 0; i < 200; ++i) wet.apply(0.0, -9.0, s);
  EXPECT_NEAR(s.a, -0.5 * kGravity, 1e-3);
}
