#include <gtest/gtest.h>

#include "fleetguard/actors.hpp"

using namespace fg;

namespace {

Scenario straight_road() {
  Scenario sc;
  sc.family = "test";
  sc.route = PathBuilder().straight(500).build();
  sc.map_route = sc.route;
  return sc;
}

}  // namespace

TEST(Actors, ConstantSpeedVehicleAdvances) {
  Scenario sc = straight_road();
  ActorSpec a;
  a.id = 1;
  a.s0 = 20;
  a.v0 = 10;
  sc.actors.push_back(a);
  ActorSim sim(sc);
  for (int i = 0; i < 100; ++i) sim.step(i * 0.05, 0.05);
  EXPECT_NEAR(sim.states()[0].s, 70.0, 1e-9);
  EXPECT_NEAR(sim.states()[0].pos.x, 70.0, 1e-9);
  EXPECT_NEAR(sim.states()[0].vel.x, 10.0, 1e-9);
}

TEST(Actors, BrakingStopsAtZero) {
  Scenario sc = straight_road();
  ActorSpec a;
  a.s0 = 0;
  a.v0 = 10;
  a.speed_changes.push_back({1.0, -5.0, 10.0});
  sc.actors.push_back(a);
  ActorSim sim(sc);
  for (int i = 0; i < 200; ++i) sim.step(i * 0.05, 0.05);
  EXPECT_DOUBLE_EQ(sim.states()[0].speed, 0.0);
  // 10 m in the first second, then v^2 / 2a = 10 m of braking (discretised)
  EXPECT_NEAR(sim.states()[0].s, 20.0, 0.6);
}

TEST(Actors, CutInEndsInEgoLane) {
  Scenario sc = straight_road();
  ActorSpec a;
  a.s0 = 30;
  a.lat0 = 3.6;
  a.lat1 = 0.0;
  a.v0 = 8;
  a.t_lat = 1.0;
  a.lat_duration = 2.0;
  sc.actors.push_back(a);
  ActorSim sim(sc);
  double max_rate = 0;
  for (int i = 0; i < 100; ++i) {
    sim.step(i * 0.05, 0.05);
    max_rate = std::max(max_rate, std::fabs(sim.states()[0].vel.y));
  }
  EXPECT_NEAR(sim.states()[0].lat, 0.0, 1e-9);
  // peak lateral speed of a half-cosine is pi/2 * distance / duration
  EXPECT_NEAR(max_rate, kPi / 2 * 3.6 / 2.0, 0.1);
}

TEST(Actors, PedestrianCrossesTheRoad) {
  Scenario sc = straight_road();
  ActorSpec p;
  p.kind = ActorKind::Pedestrian;
  p.s0 = 50;
  p.lat0 = -5.0;
  p.t_walk = 0.0;
  p.walk_speed = 1.5;
  p.length = p.width = 0.6;
  sc.actors.push_back(p);
  ActorSim sim(sc);
  for (int i = 0; i < 80; ++i) sim.step(i * 0.05, 0.05);  // 4 s
  EXPECT_NEAR(sim.states()[0].lat, 1.0, 1e-6);
  for (int i = 80; i < 400; ++i) sim.step(i * 0.05, 0.05);
  // stops once clear of the far side
  EXPECT_GT(sim.states()[0].lat, 5.0);
  EXPECT_LT(sim.states()[0].lat, 5.6);
  EXPECT_DOUBLE_EQ(sim.states()[0].s, 50.0);
}

TEST(Actors, ConesNeverMove) {
  Scenario sc = straight_road();
  ActorSpec c;
  c.kind = ActorKind::Cone;
  c.s0 = 40;
  c.lat0 = 1.0;
  sc.actors.push_back(c);
  ActorSim sim(sc);
  for (int i = 0; i < 50; ++i) sim.step(i * 0.05, 0.05);
  EXPECT_DOUBLE_EQ(sim.states()[0].pos.x, 40.0);
  EXPECT_DOUBLE_EQ(sim.states()[0].pos.y, 1.0);
}
