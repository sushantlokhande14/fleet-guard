#include <gtest/gtest.h>

#include "fleetguard/safety.hpp"

using namespace fg;

namespace {

// straight route along +x, so s == x and lat == y
const Path& road() {
  static const Path p = PathBuilder({-100, 0}, 0.0).straight(600).build();
  return p;
}

Hazard hazard(const VehicleState& ego, const std::vector<ActorState>& actors) {
  VehicleParams vp;
  return nearest_in_path(road(), road().project(ego.pos), ego, vp, actors);
}

ActorState car(Vec2 pos, double speed, double heading = 0.0) {
  ActorState a;
  a.id = 1;
  a.pos = pos;
  a.s = pos.x + 100.0;
  a.lat = pos.y;
  a.heading = heading;
  a.vel = Vec2::from_angle(heading) * speed;
  a.speed = speed;
  a.length = 4.6;
  a.width = 1.9;
  return a;
}

}  // namespace

TEST(Safety, GapAndTtcToLead) {
  VehicleParams vp;
  VehicleState ego;
  ego.v = 20;
  auto h = hazard(ego, {car({30, 0}, 10)});
  EXPECT_EQ(h.id, 1);
  EXPECT_NEAR(h.gap, 30 - 0.5 * (vp.length + 4.6), 1e-9);
  EXPECT_NEAR(h.ttc, h.gap / 10.0, 1e-9);
}

TEST(Safety, IgnoresObjectsBehindOrBeside) {
  VehicleState ego;
  ego.v = 15;
  EXPECT_EQ(hazard(ego, {car({-20, 0}, 5)}).id, -1);
  EXPECT_EQ(hazard(ego, {car({20, 3.6}, 5)}).id, -1);  // next lane
  EXPECT_EQ(hazard(ego, {car({20, 1.5}, 5)}).id, 1);   // straddling
}

TEST(Safety, OpeningGapHasNoTtc) {
  VehicleState ego;
  ego.v = 10;
  auto h = hazard(ego, {car({25, 0}, 15)});
  EXPECT_TRUE(std::isinf(h.ttc));
}

TEST(Safety, PicksNearest) {
  VehicleState ego;
  auto a = car({40, 0}, 0);
  auto b = car({20, 0.5}, 0);
  b.id = 2;
  EXPECT_EQ(hazard(ego, {a, b}).id, 2);
}

TEST(Safety, BoxCollision) {
  VehicleParams vp;
  VehicleState ego;
  EXPECT_TRUE(collides(ego, vp, car({4.0, 0}, 0)));
  EXPECT_FALSE(collides(ego, vp, car({4.8, 0}, 0)));
  EXPECT_FALSE(collides(ego, vp, car({0, 2.0}, 0)));
  // rotated 90 degrees: only its width extends along ego's axis
  EXPECT_TRUE(collides(ego, vp, car({3.0, 0}, 0, kPi / 2)));
  EXPECT_FALSE(collides(ego, vp, car({3.4, 0}, 0, kPi / 2)));
}

TEST(Safety, LaneRelativeOnCurves) {
  // a car parked on the inside of a bend is not in our lane even if it is
  // straight ahead of the bonnet
  const Path bend = PathBuilder().straight(20).arc(30, kPi / 2).straight(50).build();
  VehicleParams vp;
  VehicleState ego;
  ego.pos = bend.point_at(15);
  ego.v = 10;
  ActorState parked;
  parked.s = 40;
  parked.lat = 3.6;  // next lane over
  parked.pos = bend.point_at(40) + bend.normal_at(40) * 3.6;
  parked.length = 4.6;
  parked.width = 1.9;
  EXPECT_EQ(nearest_in_path(bend, bend.project(ego.pos), ego, vp, {parked}).id, -1);
  parked.lat = 0.3;
  parked.pos = bend.point_at(40) + bend.normal_at(40) * 0.3;
  EXPECT_EQ(nearest_in_path(bend, bend.project(ego.pos), ego, vp, {parked}).id, 0);
}
