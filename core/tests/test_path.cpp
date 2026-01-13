#include <gtest/gtest.h>

#include "fleetguard/path.hpp"

using fg::Path;
using fg::PathBuilder;
using fg::Vec2;

TEST(Path, StraightLineProjection) {
  Path p = PathBuilder({0, 0}, 0.0).straight(100).build();
  EXPECT_NEAR(p.length(), 100.0, 1e-9);

  auto pr = p.project({40.0, 2.0});
  EXPECT_NEAR(pr.s, 40.0, 1e-9);
  EXPECT_NEAR(pr.lateral, 2.0, 1e-9);  // left is positive

  pr = p.project({60.0, -1.5});
  EXPECT_NEAR(pr.s, 60.0, 1e-9);
  EXPECT_NEAR(pr.lateral, -1.5, 1e-9);
}

TEST(Path, ProjectionBeyondEndsExtrapolates) {
  Path p = PathBuilder({0, 0}, 0.0).straight(10).build();
  EXPECT_NEAR(p.project({-5, 0}).s, -5.0, 1e-9);
  EXPECT_NEAR(p.project({15, 1}).s, 15.0, 1e-9);
}

TEST(Path, PointAndHeading) {
  Path p = PathBuilder({0, 0}, fg::kPi / 2).straight(50).build();
  Vec2 q = p.point_at(20);
  EXPECT_NEAR(q.x, 0.0, 1e-9);
  EXPECT_NEAR(q.y, 20.0, 1e-9);
  EXPECT_NEAR(p.heading_at(20), fg::kPi / 2, 1e-9);
  EXPECT_NEAR(p.normal_at(20).x, -1.0, 1e-9);
}

TEST(Path, ArcCurvatureMatchesRadius) {
  const double R = 25.0;
  Path left = PathBuilder({0, 0}, 0.0, 0.5).arc(R, fg::kPi / 2).build();
  EXPECT_NEAR(left.length(), R * fg::kPi / 2, 0.05);
  EXPECT_NEAR(left.curvature_at(left.length() / 2), 1.0 / R, 1e-3);

  Path right = PathBuilder({0, 0}, 0.0, 0.5).arc(R, -fg::kPi / 2).build();
  EXPECT_NEAR(right.curvature_at(right.length() / 2), -1.0 / R, 1e-3);
  // quarter turn to the right ends heading south
  EXPECT_NEAR(right.heading_at(right.length() - 0.1), -fg::kPi / 2, 0.03);
  EXPECT_NEAR(right.points().back().x, R, 1e-6);
  EXPECT_NEAR(right.points().back().y, -R, 1e-6);
}

TEST(Path, MaxCurvatureWindow) {
  Path p = PathBuilder({0, 0}, 0.0).straight(50).arc(20, 0.8).straight(50).build();
  EXPECT_NEAR(p.max_abs_curvature(0, 40), 0.0, 1e-6);
  EXPECT_NEAR(p.max_abs_curvature(0, p.length()), 1.0 / 20, 2e-3);
}

TEST(Path, LaneShiftRestoresHeading) {
  Path p = PathBuilder({0, 0}, 0.0).straight(20).lane_shift(40, 3.0).straight(20).build();
  const Vec2 end = p.points().back();
  EXPECT_NEAR(end.y, 3.0, 1e-9);
  EXPECT_NEAR(p.heading_at(p.length() - 1), 0.0, 1e-9);
  // mid-shift the path is half way across
  EXPECT_NEAR(p.project({40, 0}).lateral, -1.5, 0.05);
}

TEST(Path, OffsetPathIsParallel) {
  Path p = PathBuilder({0, 0}, 0.0).straight(30).arc(40, 0.6).straight(30).build();
  Path q = p.offset(1.5);
  for (double s = 5; s < p.length() - 5; s += 7) {
    auto pr = p.project(q.point_at(s * q.length() / p.length()));
    EXPECT_NEAR(pr.lateral, 1.5, 0.05) << "at s=" << s;
  }
}

TEST(Path, WindowedProjectionMatchesFullSearch) {
  Path p = PathBuilder({0, 0}, 0.0).straight(100).arc(30, 1.2).straight(100).build();
  size_t hint = Path::npos;
  for (double s = 0; s < p.length(); s += 3.0) {
    Vec2 q = p.point_at(s) + p.normal_at(s) * 0.7;
    auto windowed = p.project(q, hint);
    auto full = p.project(q);
    EXPECT_NEAR(windowed.s, full.s, 1e-9);
    hint = windowed.segment;
  }
}

TEST(Path, RejectsDegenerateInput) {
  EXPECT_THROW(Path({{0, 0}, {0, 0}}), std::invalid_argument);
}
