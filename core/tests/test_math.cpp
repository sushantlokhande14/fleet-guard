#include <gtest/gtest.h>

#include "fleetguard/math.hpp"

using fg::Vec2;

TEST(Math, VectorOps) {
  Vec2 a{3, 4};
  EXPECT_DOUBLE_EQ(a.norm(), 5.0);
  EXPECT_DOUBLE_EQ(a.dot({1, 0}), 3.0);
  EXPECT_DOUBLE_EQ(Vec2(1, 0).cross({0, 1}), 1.0);
  EXPECT_DOUBLE_EQ(Vec2(1, 0).cross({0, -1}), -1.0);
  Vec2 n = a.normalized();
  EXPECT_NEAR(n.norm(), 1.0, 1e-12);
  EXPECT_DOUBLE_EQ(Vec2(0, 0).normalized().norm(), 0.0);
}

TEST(Math, PerpIsLeftNormal) {
  Vec2 heading{1, 0};
  Vec2 left = heading.perp();
  EXPECT_DOUBLE_EQ(left.x, 0.0);
  EXPECT_DOUBLE_EQ(left.y, 1.0);
  EXPECT_GT(heading.cross(left), 0.0);
}

TEST(Math, Rotation) {
  Vec2 r = Vec2(1, 0).rotated(fg::kPi / 2);
  EXPECT_NEAR(r.x, 0.0, 1e-12);
  EXPECT_NEAR(r.y, 1.0, 1e-12);
  EXPECT_NEAR(Vec2::from_angle(0.3).angle(), 0.3, 1e-12);
}

TEST(Math, WrapAngle) {
  // +pi and -pi are the same heading; remainder() may return either
  EXPECT_NEAR(std::fabs(fg::wrap_angle(3 * fg::kPi)), fg::kPi, 1e-9);
  EXPECT_NEAR(std::fabs(fg::wrap_angle(-3 * fg::kPi)), fg::kPi, 1e-9);
  EXPECT_NEAR(fg::wrap_angle(2 * fg::kPi + 0.25), 0.25, 1e-12);
  EXPECT_NEAR(fg::wrap_angle(-0.25), -0.25, 1e-12);
}

TEST(Math, ClampLerpSign) {
  EXPECT_DOUBLE_EQ(fg::clamp(5, 0, 1), 1);
  EXPECT_DOUBLE_EQ(fg::clamp(-5, 0, 1), 0);
  EXPECT_DOUBLE_EQ(fg::lerp(2, 4, 0.5), 3);
  EXPECT_DOUBLE_EQ(fg::sign(-2.0), -1.0);
  EXPECT_DOUBLE_EQ(fg::sign(0.0), 0.0);
}
