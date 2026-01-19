#include <gtest/gtest.h>

#include "fleetguard/build_config.hpp"

using namespace fg;
using nlohmann::json;

TEST(BuildConfig, EmptyDocumentGivesDefaults) {
  BuildConfig b = build_from_json(json::object());
  BuildConfig d;
  EXPECT_EQ(build_to_json(b), build_to_json(d));
}

TEST(BuildConfig, OverlayChangesOnlyNamedFields) {
  json j = {{"name", "rc-2"}, {"planner", {{"headway_s", 1.1}, {"use_live_lane", false}}}, {"control", {{"steer_gain", 1.4}}}};
  BuildConfig b = build_from_json(j);
  EXPECT_EQ(b.name, "rc-2");
  EXPECT_DOUBLE_EQ(b.planner.headway_s, 1.1);
  EXPECT_FALSE(b.planner.use_live_lane);
  EXPECT_DOUBLE_EQ(b.control.steer_gain, 1.4);
  EXPECT_DOUBLE_EQ(b.planner.min_gap_m, PlannerParams{}.min_gap_m);
  EXPECT_DOUBLE_EQ(b.perception.latency_ms, PerceptionParams{}.latency_ms);
}

TEST(BuildConfig, RoundTrip) {
  json j = {{"perception", {{"confirm_frames", 4}, {"fp_rate", 0.01}}}};
  BuildConfig b = build_from_json(j);
  BuildConfig b2 = build_from_json(build_to_json(b));
  EXPECT_EQ(build_to_json(b), build_to_json(b2));
  EXPECT_EQ(b2.perception.confirm_frames, 4);
}

TEST(BuildConfig, UnknownKeysThrow) {
  EXPECT_THROW(build_from_json({{"planner", {{"headway", 1.0}}}}), std::invalid_argument);
  EXPECT_THROW(build_from_json({{"radar", json::object()}}), std::invalid_argument);
  EXPECT_THROW(build_from_json({{"planner", {{"headway_s", "fast"}}}}), std::invalid_argument);
  EXPECT_THROW(build_from_json(json::array()), std::invalid_argument);
}

TEST(BuildConfig, InformationalKeysAreIgnored) {
  BuildConfig b = build_from_json({{"description", "nightly"}, {"parent", "baseline"}});
  EXPECT_EQ(b.name, "baseline");
}
