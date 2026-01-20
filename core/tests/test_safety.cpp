#include <gtest/gtest.h>

#include "fleetguard/safety.hpp"

using namespace fg;

namespace {

ActorState car(Vec2 pos, double speed, double heading = 0.0) {
  ActorState a;
  a.id = 1;
  a.pos = pos;
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
  auto h = nearest_in_path(ego, vp, {car({30, 0}, 10)});
  EXPECT_EQ(h.id, 1);
  EXPECT_NEAR(h.gap, 30 - 0.5 * (vp.length + 4.6), 1e-9);
  EXPECT_NEAR(h.ttc, h.gap / 10.0, 1e-9);
}

TEST(Safety, IgnoresObjectsBehindOrBeside) {
  VehicleParams vp;
  VehicleState ego;
  ego.v = 15;
  EXPECT_EQ(nearest_in_path(ego, vp, {car({-20, 0}, 5)}).id, -1);
  EXPECT_EQ(nearest_in_path(ego, vp, {car({20, 3.6}, 5)}).id, -1);  // next lane
  EXPECT_EQ(nearest_in_path(ego, vp, {car({20, 1.5}, 5)}).id, 1);   // straddling
}

TEST(Safety, OpeningGapHasNoTtc) {
  VehicleParams vp;
  VehicleState ego;
  ego.v = 10;
  auto h = nearest_in_path(ego, vp, {car({25, 0}, 15)});
  EXPECT_TRUE(std::isinf(h.ttc));
}

TEST(Safety, PicksNearest) {
  VehicleParams vp;
  VehicleState ego;
  auto a = car({40, 0}, 0);
  auto b = car({20, 0.5}, 0);
  b.id = 2;
  EXPECT_EQ(nearest_in_path(ego, vp, {a, b}).id, 2);
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
