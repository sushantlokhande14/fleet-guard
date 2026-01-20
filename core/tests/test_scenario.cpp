#include <gtest/gtest.h>

#include "fleetguard/scenario.hpp"

using namespace fg;

TEST(Scenario, FamiliesAreRegistered) {
  const auto& fams = scenario_families();
  EXPECT_EQ(fams.size(), 7u);
  for (const auto& f : fams) EXPECT_TRUE(is_family(f));
  EXPECT_FALSE(is_family("teleport"));
  EXPECT_THROW(make_scenario("teleport", 1), std::invalid_argument);
}

TEST(Scenario, SameSeedSameScenario) {
  for (const auto& f : scenario_families()) {
    const auto a = make_scenario(f, 77).describe();
    const auto b = make_scenario(f, 77).describe();
    EXPECT_EQ(a.dump(), b.dump()) << f;
    const auto c = make_scenario(f, 78).describe();
    EXPECT_NE(a.dump(), c.dump()) << f;
  }
}

TEST(Scenario, GeneratedScenariosAreSane) {
  for (const auto& f : scenario_families()) {
    for (uint64_t seed = 0; seed < 200; ++seed) {
      const Scenario sc = make_scenario(f, seed);
      ASSERT_FALSE(sc.route.empty());
      EXPECT_GT(sc.route.length(), 150.0) << sc.id();
      EXPECT_GT(sc.ego_v0, 0.0);
      EXPECT_LE(sc.ego_v0, sc.default_limit + 1e-9);
      EXPECT_GT(sc.time_limit, sc.route.length() / sc.default_limit);
      EXPECT_GT(sc.friction, 0.5);
      for (const auto& a : sc.actors) {
        EXPECT_GE(a.s0, 0.0);
        EXPECT_GT(a.length, 0.0);
      }
    }
  }
}

TEST(Scenario, IdEncodesFamilyAndSeed) {
  EXPECT_EQ(make_scenario("highway_follow", 12).id(), "highway_follow-12");
}

TEST(Scenario, WeatherMixCoversAllKinds) {
  int counts[3] = {0, 0, 0};
  for (uint64_t seed = 0; seed < 500; ++seed) counts[static_cast<int>(make_scenario("s_curve", seed).weather)]++;
  EXPECT_GT(counts[0], 300);
  EXPECT_GT(counts[1], 50);
  EXPECT_GT(counts[2], 20);
}

TEST(Scenario, ConstructionMapDiffersFromLiveLane) {
  for (uint64_t seed = 0; seed < 20; ++seed) {
    const Scenario sc = make_scenario("construction_shift", seed);
    // the prior map runs straight through the work zone
    double max_dev = 0;
    for (double s = 0; s < sc.map_route.length(); s += 5) max_dev = std::max(max_dev, std::fabs(sc.route.project(sc.map_route.point_at(s)).lateral));
    EXPECT_GT(max_dev, 2.7) << sc.id();
    int cones = 0;
    for (const auto& a : sc.actors) cones += a.kind == ActorKind::Cone;
    EXPECT_GE(cones, 5) << sc.id();
    EXPECT_LT(sc.speed_limit_at(sc.route.length() / 2), sc.default_limit);
    EXPECT_TRUE(sc.geometry().contains("map_route"));
  }
}

TEST(Scenario, IntersectionTurnIsAQuarterTurn) {
  const Scenario sc = make_scenario("intersection_turn", 5);
  const double h0 = sc.route.heading_at(1.0);
  const double h1 = sc.route.heading_at(sc.route.length() - 1.0);
  EXPECT_NEAR(std::fabs(wrap_angle(h1 - h0)), kPi / 2, 0.02);
}

TEST(Scenario, GeometryExport) {
  const Scenario sc = make_scenario("s_curve", 3);
  const auto g = sc.geometry(5.0);
  ASSERT_TRUE(g.contains("route"));
  EXPECT_GT(g["route"].size(), sc.route.length() / 5.0);
  EXPECT_FALSE(g.contains("map_route"));  // map matches the road outside work zones
}
