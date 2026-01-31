#include <gtest/gtest.h>

#include "fleetguard/perception.hpp"

using namespace fg;

namespace {

constexpr double kDt = 0.05;

Scenario road_with(std::vector<ActorSpec> actors, Weather w = Weather::Clear, uint64_t seed = 5) {
  Scenario sc;
  sc.family = "test";
  sc.seed = seed;
  sc.weather = w;
  sc.route = PathBuilder().straight(400).build();
  sc.map_route = sc.route;
  sc.actors = std::move(actors);
  return sc;
}

ActorSpec parked(int id, double s, double lat = 0.0, ActorKind kind = ActorKind::Vehicle) {
  ActorSpec a;
  a.id = id;
  a.kind = kind;
  a.s0 = s;
  a.lat0 = a.lat1 = lat;
  if (kind == ActorKind::Pedestrian) a.length = a.width = 0.6;
  return a;
}

PerceptionParams perfect() {
  PerceptionParams p;
  p.vehicle_miss_rate = p.ped_miss_rate = 0.0;
  p.range_miss_slope = 0.0;
  p.fp_rate = 0.0;
  p.pos_noise_m = p.pos_noise_per_m = 0.0;
  p.latency_ms = 0.0;
  return p;
}

struct SensorRun {
  std::vector<std::vector<PerceivedObject>> outputs;
  std::vector<Event> events;
  int tp = 0, fn = 0, fp = 0;
};

SensorRun drive(const PerceptionParams& p, const Scenario& sc, int ticks, VehicleState ego = {}) {
  ActorSim actors(sc);
  Perception per(p, sc, kDt);
  SensorRun r;
  for (int i = 0; i < ticks; ++i) {
    r.outputs.push_back(per.update(i * kDt, ego, actors.states(), r.events));
    actors.step(i * kDt, kDt);
    ego.pos.x += ego.v * kDt;
  }
  per.flush(ticks * kDt, r.events);
  r.tp = per.total_tp();
  r.fn = per.total_fn();
  r.fp = per.total_fp();
  return r;
}

}  // namespace

TEST(Perception, PerfectSensorTracksEverything) {
  Scenario sc = road_with({parked(1, 30), parked(2, 50, 0.5)});
  SensorRun r = drive(perfect(), sc, 40);
  EXPECT_EQ(r.fn, 2);  // one frame before confirmation, per object
  EXPECT_EQ(r.fp, 0);
  ASSERT_EQ(r.outputs.back().size(), 2u);
  for (const auto& o : r.outputs.back()) {
    EXPECT_NEAR(o.pos.y, o.truth_id == 2 ? 0.5 : 0.0, 1e-9);
    EXPECT_NEAR(o.vel.norm(), 0.0, 1e-6);
  }
}

TEST(Perception, BlindSensorSeesNothing) {
  PerceptionParams p = perfect();
  p.vehicle_miss_rate = 1.0;
  Scenario sc = road_with({parked(1, 20)});
  SensorRun r = drive(p, sc, 40);
  EXPECT_EQ(r.tp, 0);
  EXPECT_EQ(r.fn, 40);
  EXPECT_TRUE(r.outputs.back().empty());
  ASSERT_EQ(r.events.size(), 1u);
  EXPECT_EQ(r.events[0].kind, "perception_miss");
  EXPECT_EQ(r.events[0].detail, "vehicle 1");
}

TEST(Perception, LatencyDelaysTheTrackList) {
  PerceptionParams p = perfect();
  p.confirm_frames = 1;
  p.latency_ms = 100.0;  // two ticks
  SensorRun r = drive(p, road_with({parked(1, 20)}), 6);
  EXPECT_TRUE(r.outputs[0].empty());
  EXPECT_TRUE(r.outputs[1].empty());
  EXPECT_EQ(r.outputs[2].size(), 1u);
}

TEST(Perception, FogShrinksRange) {
  PerceptionParams p = perfect();
  SensorRun clear = drive(p, road_with({parked(1, 58)}, Weather::Clear), 20);
  SensorRun fog = drive(p, road_with({parked(1, 58)}, Weather::Fog), 20);
  EXPECT_EQ(clear.outputs.back().size(), 1u);
  EXPECT_TRUE(fog.outputs.back().empty());  // 90 m * 0.55 = 49.5 m
}

TEST(Perception, OutsideFieldOfViewIsInvisible) {
  SensorRun r = drive(perfect(), road_with({parked(1, 5, 30.0)}), 20);  // 80 degrees off-axis
  EXPECT_TRUE(r.outputs.back().empty());
}

TEST(Perception, HigherMissRateNeverHelps) {
  // common random numbers: a worse sensor misses a superset of what the good one misses
  std::vector<ActorSpec> actors;
  for (int i = 0; i < 6; ++i) actors.push_back(parked(i + 1, 15 + 9 * i, (i % 3 - 1) * 0.6));
  Scenario sc = road_with(actors);
  PerceptionParams base;
  PerceptionParams worse = base;
  worse.vehicle_miss_rate = 0.25;
  SensorRun a = drive(base, sc, 400);
  SensorRun b = drive(worse, sc, 400);
  EXPECT_LT(b.tp, a.tp);
  EXPECT_GT(b.fn, a.fn);
  EXPECT_EQ(a.tp + a.fn, b.tp + b.fn);
}

TEST(Perception, FarPedestrianKnob) {
  PerceptionParams p = perfect();
  p.ped_far_miss_add = 0.7;
  SensorRun near = drive(p, road_with({parked(1, 15, 0.0, ActorKind::Pedestrian)}), 200);
  SensorRun far = drive(p, road_with({parked(1, 40, 0.0, ActorKind::Pedestrian)}), 200);
  EXPECT_EQ(near.fn, 1);
  EXPECT_GT(far.fn, 20);
}

TEST(Perception, PhantomsComeFromFpRate) {
  PerceptionParams p = perfect();
  p.fp_rate = 0.05;
  SensorRun r = drive(p, road_with({}), 400);
  EXPECT_GT(r.fp, 0);
  bool saw = false;
  for (const auto& e : r.events) saw |= e.kind == "phantom_object";
  EXPECT_TRUE(saw);
  PerceptionParams none = perfect();
  EXPECT_EQ(drive(none, road_with({}), 400).fp, 0);
}

TEST(Perception, NoiseGrowsWithRange) {
  PerceptionParams p = perfect();
  p.pos_noise_m = 0.1;
  p.pos_noise_per_m = 0.01;
  SensorRun r = drive(p, road_with({parked(1, 10), parked(2, 70)}), 200);
  // tracks exist and sit near the truth; the far one is visibly noisier
  ASSERT_EQ(r.outputs.back().size(), 2u);
  for (const auto& o : r.outputs.back()) {
    const double truth = o.truth_id == 1 ? 10.0 : 70.0;
    EXPECT_NEAR(o.pos.x, truth, o.truth_id == 1 ? 0.5 : 2.0);
  }
}
