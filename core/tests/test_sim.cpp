#include <gtest/gtest.h>

#include "fleetguard/sim.hpp"

using namespace fg;

TEST(Sim, PercentileInterpolates) {
  EXPECT_DOUBLE_EQ(percentile({}, 0.5), 0.0);
  EXPECT_DOUBLE_EQ(percentile({3, 1, 2}, 0.5), 2.0);
  EXPECT_DOUBLE_EQ(percentile({1, 2, 3, 4}, 1.0), 4.0);
  EXPECT_DOUBLE_EQ(percentile({0, 10}, 0.25), 2.5);
}

TEST(Sim, EmptyRoadCompletes) {
  for (const auto& fam : {"s_curve", "highway_follow"}) {
    for (uint64_t seed = 0; seed < 10; ++seed) {
      Scenario sc = make_scenario(fam, seed);
      sc.actors.clear();  // no traffic yet: pure route following
      DriveResult r = run_drive(sc, BuildConfig{});
      EXPECT_EQ(r.summary.outcome, "completed") << sc.id();
      EXPECT_LT(r.summary.cte_max, 0.6) << sc.id();
      EXPECT_GT(r.summary.mean_speed, 5.0);
      // planned at 2.2 m/s^2; steering corrections at curve entry add some on top
      EXPECT_LE(r.summary.lat_acc_max, 4.0) << sc.id();
    }
  }
}

TEST(Sim, DeterministicReplay) {
  Scenario sc = make_scenario("s_curve", 11);
  DriveResult a = run_drive(sc, BuildConfig{});
  DriveResult b = run_drive(sc, BuildConfig{});
  ASSERT_EQ(a.frames.size(), b.frames.size());
  for (size_t i = 0; i < a.frames.size(); ++i) {
    EXPECT_EQ(a.frames[i].x, b.frames[i].x);
    EXPECT_EQ(a.frames[i].v, b.frames[i].v);
  }
}

TEST(Sim, FramesLoggedAtTenHertz) {
  Scenario sc = make_scenario("s_curve", 2);
  sc.actors.clear();
  DriveResult r = run_drive(sc, BuildConfig{});
  ASSERT_GT(r.frames.size(), 10u);
  EXPECT_NEAR(r.frames[1].t - r.frames[0].t, 0.1, 1e-9);
  SimOptions quiet;
  quiet.record_frames = false;
  EXPECT_TRUE(run_drive(sc, BuildConfig{}, quiet).frames.empty());
}
