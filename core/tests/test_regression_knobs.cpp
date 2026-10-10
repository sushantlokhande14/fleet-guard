// Each class of regression the platform is meant to catch has to leave a
// measurable signature in the drive summaries and events. These tests drive a
// small scenario set with the baseline and with one knob turned, and check the
// signature appears in aggregate.
#include <gtest/gtest.h>

#include <map>
#include <string>

#include "fleetguard/sim.hpp"

using namespace fg;

namespace {

struct Agg {
  int drives = 0;
  int failures = 0;
  std::map<std::string, int> reasons;
  std::map<std::string, int> events;
  double recall = 0, cte_max = 0, steer_rev = 0, accel_rev = 0;
  int deadline_misses = 0;
};

Agg drive_set(const std::string& family, const BuildConfig& b, int n = 30) {
  Agg a;
  for (int seed = 0; seed < n; ++seed) {
    SimOptions opt;
    opt.record_frames = false;
    const DriveResult r = run_drive(make_scenario(family, 1000 + seed), b, opt);
    a.drives++;
    if (r.summary.outcome != "completed") {
      a.failures++;
      a.reasons[r.summary.reason]++;
    }
    for (const auto& e : r.events) a.events[e.kind]++;
    a.recall += r.summary.recall / n;
    a.cte_max += r.summary.cte_max / n;
    a.steer_rev += r.summary.steer_reversal_rate / n;
    a.accel_rev += r.summary.accel_reversal_rate / n;
    a.deadline_misses += r.summary.deadline_misses;
  }
  return a;
}

}  // namespace

TEST(RegressionKnobs, PerceptionMissesFarPedestrians) {
  BuildConfig bad;
  bad.perception.ped_far_miss_add = 0.95;
  bad.perception.ped_far_range_m = 20.0;
  Agg base = drive_set("ped_crossing", BuildConfig{});
  Agg reg = drive_set("ped_crossing", bad);
  EXPECT_LT(reg.recall, base.recall - 0.05);
  EXPECT_GT(reg.events["perception_miss"], base.events["perception_miss"]);
}

TEST(RegressionKnobs, LatencySpikesTripTheWatchdog) {
  BuildConfig bad;
  bad.planner.spike_prob = 0.08;
  Agg base = drive_set("urban_cut_in", BuildConfig{});
  Agg reg = drive_set("urban_cut_in", bad);
  EXPECT_GT(reg.deadline_misses, 5 * std::max(1, base.deadline_misses));
  EXPECT_GT(reg.reasons["planner_watchdog"], base.reasons["planner_watchdog"]);
}

TEST(RegressionKnobs, CurveOffsetLeavesTheLane) {
  BuildConfig bad;
  bad.planner.curve_offset_m = 0.9;
  Agg base = drive_set("s_curve", BuildConfig{});
  Agg reg = drive_set("s_curve", bad);
  EXPECT_GT(reg.cte_max, base.cte_max + 0.4);
  EXPECT_GT(reg.events["off_route"], base.events["off_route"]);
}

TEST(RegressionKnobs, StaleMapInWorkZones) {
  BuildConfig bad;
  bad.planner.use_live_lane = false;
  Agg base = drive_set("construction_shift", BuildConfig{});
  Agg reg = drive_set("construction_shift", bad);
  EXPECT_EQ(base.failures, 0);
  EXPECT_GT(reg.failures, 25);
}

TEST(RegressionKnobs, SteeringGainOscillates) {
  BuildConfig bad;
  bad.control.steer_gain = 1.8;
  bad.control.actuator_delay_ms = 130;
  Agg base = drive_set("highway_follow", BuildConfig{});
  Agg reg = drive_set("highway_follow", bad);
  EXPECT_GT(reg.steer_rev, base.steer_rev * 2 + 0.05);
  EXPECT_GT(reg.events["steer_oscillation"], base.events["steer_oscillation"]);
}

TEST(RegressionKnobs, AggressiveSpeedLoopRings) {
  BuildConfig bad;
  bad.control.speed_kp = 6.0;
  bad.control.actuator_delay_ms = 120;
  Agg base = drive_set("stop_and_go", BuildConfig{});
  Agg reg = drive_set("stop_and_go", bad);
  EXPECT_GT(reg.accel_rev, base.accel_rev * 1.5);
  EXPECT_GT(reg.events["accel_oscillation"], base.events["accel_oscillation"]);
}

TEST(RegressionKnobs, ShortHeadwayCausesTakeovers) {
  BuildConfig bad;
  bad.planner.headway_s = 0.7;
  bad.planner.min_gap_m = 2.0;
  Agg base = drive_set("stop_and_go", BuildConfig{});
  Agg reg = drive_set("stop_and_go", bad);
  EXPECT_GT(reg.reasons["ttc_takeover"], base.reasons["ttc_takeover"] + 3);
}

TEST(RegressionKnobs, NoPedestrianYieldCausesTakeovers) {
  BuildConfig bad;
  bad.planner.yield_to_crossing_peds = false;
  Agg base = drive_set("ped_crossing", BuildConfig{});
  Agg reg = drive_set("ped_crossing", bad);
  EXPECT_GT(reg.failures, base.failures + 8);
  // perception is untouched: the misses are the planner's
  EXPECT_NEAR(reg.recall, base.recall, 0.01);
}
