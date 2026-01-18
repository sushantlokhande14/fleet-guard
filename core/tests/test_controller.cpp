#include <gtest/gtest.h>

#include <cmath>

#include "fleetguard/controller.hpp"

using namespace fg;

namespace {

struct Loop {
  VehicleParams vp;
  ControllerParams cp;
  double dt = 0.05;
  double friction = 0.9;

  // run closed loop on `path` at constant v_ref; returns max |lateral| over the last `tail` seconds
  // and counts steering-rate sign reversals in that window
  struct Result {
    double tail_max_lat;
    int reversals;
    VehicleState final;
  };

  Result run(const Path& path, VehicleState s, double v_ref, double seconds, double tail = 5.0) {
    Controller ctl(cp, vp, dt);
    Actuators act(vp, cp.actuator_delay_ms / 1000.0, dt, friction);
    Result r{0.0, 0, s};
    double last_steer = s.steer, last_rate = 0.0;
    const int n = static_cast<int>(seconds / dt);
    for (int i = 0; i < n; ++i) {
      ControlTarget tgt{&path, 0.0, 0.0, v_ref};
      const auto out = ctl.update(s, tgt);
      act.apply(out.steer_cmd, out.accel_cmd, s);
      step_vehicle(s, vp, dt);
      if (i * dt > seconds - tail) {
        r.tail_max_lat = std::max(r.tail_max_lat, std::fabs(path.project(s.pos).lateral));
        const double rate = (s.steer - last_steer) / dt;
        if (std::fabs(rate) > 0.02 && rate * last_rate < 0) r.reversals++;
        if (std::fabs(rate) > 0.02) last_rate = rate;
      }
      last_steer = s.steer;
    }
    r.final = s;
    return r;
  }
};

}  // namespace

TEST(Controller, ConvergesOntoStraightLane) {
  Loop loop;
  Path p = PathBuilder().straight(800).build();
  VehicleState s;
  s.pos = {0, 1.5};
  s.v = 15;
  auto r = loop.run(p, s, 15, 20);
  EXPECT_LT(r.tail_max_lat, 0.05);
  EXPECT_NEAR(r.final.yaw, 0.0, 0.01);
  EXPECT_NEAR(r.final.v, 15.0, 0.05);
}

TEST(Controller, TracksCurveWithSmallError) {
  Loop loop;
  Path p = PathBuilder().straight(50).arc(80, 1.2).straight(200).build();
  VehicleState s;
  s.v = 12;
  Controller ctl(loop.cp, loop.vp, loop.dt);
  Actuators act(loop.vp, 0.04, loop.dt, 0.9);
  double worst = 0;
  for (int i = 0; i < 400; ++i) {
    auto out = ctl.update(s, {&p, 0.0, 0.0, 12.0});
    act.apply(out.steer_cmd, out.accel_cmd, s);
    step_vehicle(s, loop.vp, loop.dt);
    worst = std::max(worst, std::fabs(p.project(s.pos).lateral));
  }
  // pure pursuit cuts corners a little; it must stay well inside the lane
  EXPECT_LT(worst, 0.5);
}

TEST(Controller, LateralOffsetIsHonoured) {
  Loop loop;
  Path p = PathBuilder().straight(800).build();
  VehicleState s;
  s.v = 15;
  Controller ctl(loop.cp, loop.vp, loop.dt);
  Actuators act(loop.vp, 0.04, loop.dt, 0.9);
  for (int i = 0; i < 400; ++i) {
    auto out = ctl.update(s, {&p, 0.8, 0.0, 15.0});
    act.apply(out.steer_cmd, out.accel_cmd, s);
    step_vehicle(s, loop.vp, loop.dt);
  }
  EXPECT_NEAR(p.project(s.pos).lateral, 0.8, 0.05);
}

TEST(Controller, SpeedTrackingFromStandstill) {
  Loop loop;
  Path p = PathBuilder().straight(1000).build();
  auto r = loop.run(p, VehicleState{}, 20.0, 25);
  EXPECT_NEAR(r.final.v, 20.0, 0.1);
}

TEST(Controller, HighGainWithDelayOscillates) {
  // the failure mode behind control-instability regressions
  Path p = PathBuilder().straight(1500).build();
  VehicleState s;
  s.pos = {0, 0.5};
  s.v = 25;

  Loop good;
  auto stable = good.run(p, s, 25, 20, 10);

  Loop bad;
  bad.cp.steer_gain = 2.6;
  bad.cp.actuator_delay_ms = 160;
  auto unstable = bad.run(p, s, 25, 20, 10);

  EXPECT_LT(stable.tail_max_lat, 0.05);
  EXPECT_GT(unstable.tail_max_lat, 5 * stable.tail_max_lat + 0.05);
  EXPECT_GT(unstable.reversals, stable.reversals + 4);
}
