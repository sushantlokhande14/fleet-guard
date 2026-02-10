#include <gtest/gtest.h>

#include "fleetguard/compare.hpp"
#include "fleetguard/sim.hpp"

using namespace fg;

namespace {

DriveResult synthetic(double lat, double v, double length = 100.0, double t_offset = 0.0) {
  DriveResult r;
  r.summary.build = "x";
  for (double s = 0; s <= length; s += v * 0.1) {
    Frame f;
    f.s = s;
    f.t = s / v + t_offset;
    f.cte = lat;
    f.v = v;
    r.frames.push_back(f);
  }
  return r;
}

}  // namespace

TEST(Compare, IdenticalDrivesHaveNoDifference) {
  Scenario sc = make_scenario("urban_cut_in", 8);
  DriveResult a = run_drive(sc, BuildConfig{});
  DriveResult b = run_drive(sc, BuildConfig{});
  PairMetrics p = compare_drives(a, b);
  EXPECT_DOUBLE_EQ(p.lat_max_abs_diff, 0.0);
  EXPECT_DOUBLE_EQ(p.speed_rmse, 0.0);
  EXPECT_DOUBLE_EQ(p.time_delta_s, 0.0);
  EXPECT_LT(p.first_divergence_s, 0.0);
  EXPECT_FALSE(p.outcome_changed);
  EXPECT_GT(p.common_s, 100.0);
}

TEST(Compare, LateralOffsetIsMeasuredAlongTheRoute) {
  PairMetrics p = compare_drives(synthetic(0.0, 10.0), synthetic(0.5, 10.0));
  EXPECT_NEAR(p.lat_mean_abs_diff, 0.5, 1e-9);
  EXPECT_NEAR(p.lat_max_abs_diff, 0.5, 1e-9);
  EXPECT_NEAR(p.first_divergence_s, 0.0, 1e-9);
}

TEST(Compare, SlowerCandidateIsNotOffCourse) {
  PairMetrics p = compare_drives(synthetic(0.0, 10.0), synthetic(0.0, 8.0));
  EXPECT_NEAR(p.lat_max_abs_diff, 0.0, 1e-12);
  EXPECT_NEAR(p.speed_rmse, 2.0, 1e-9);
  EXPECT_NEAR(p.time_delta_s, 100.0 / 8.0 - 100.0 / 10.0, 0.05);
}

TEST(Compare, CommonRangeStopsWhereTheShorterDriveEnds) {
  PairMetrics p = compare_drives(synthetic(0.0, 10.0, 200.0), synthetic(0.0, 10.0, 80.0));
  EXPECT_NEAR(p.common_s, 80.0, 1.0);
}

TEST(Compare, RegressedControlShowsUpInDeltas) {
  Scenario sc = make_scenario("s_curve", 4);
  BuildConfig cand;
  cand.name = "rc";
  cand.control.steer_gain = 1.9;
  cand.control.actuator_delay_ms = 120;
  DriveResult a = run_drive(sc, BuildConfig{});
  DriveResult b = run_drive(sc, cand);
  PairMetrics p = compare_drives(a, b);
  EXPECT_EQ(p.candidate, "rc");
  EXPECT_GT(p.d_steer_reversal_rate, 0.0);
  EXPECT_GT(p.lat_max_abs_diff, 0.1);
}

TEST(Compare, BiasedBuildDivergesEarly) {
  Scenario sc = make_scenario("highway_follow", 2);
  BuildConfig cand;
  cand.planner.lateral_bias_m = 0.5;
  PairMetrics p = compare_drives(run_drive(sc, BuildConfig{}), run_drive(sc, cand));
  EXPECT_NEAR(p.lat_mean_abs_diff, 0.5, 0.1);
  ASSERT_GE(p.first_divergence_s, 0.0);
  EXPECT_LT(p.first_divergence_s, 60.0);  // as soon as the controller has moved over
}

TEST(Compare, JsonHasNullDivergenceWhenNone) {
  PairMetrics p;
  auto j = pair_to_json(p);
  EXPECT_TRUE(j["first_divergence_s"].is_null());
  EXPECT_FALSE(j["outcome_changed"].get<bool>());
}
