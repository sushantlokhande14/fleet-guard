#include <gtest/gtest.h>

#include "fleetguard/controller.hpp"
#include "fleetguard/planner.hpp"

using namespace fg;

namespace {

Scenario straight(double limit = 20.0) {
  Scenario sc;
  sc.family = "test";
  sc.route = PathBuilder().straight(2000).build();
  sc.map_route = sc.route;
  sc.default_limit = limit;
  return sc;
}

PerceivedObject object_at(Vec2 pos, Vec2 vel, ActorKind kind = ActorKind::Vehicle, int id = 1) {
  PerceivedObject o;
  o.track_id = id;
  o.truth_id = id;
  o.kind = kind;
  o.pos = pos;
  o.vel = vel;
  o.length = kind == ActorKind::Pedestrian ? 0.6 : 4.6;
  o.width = kind == ActorKind::Pedestrian ? 0.6 : 1.9;
  return o;
}

// Closed loop with perfect perception of one scripted object.
struct Follow {
  double final_v = 0, final_gap = 0, min_gap = 1e9;
};

Follow follow(const PlannerParams& pp, double ego_v, double lead_s, double lead_v, double seconds) {
  Scenario sc = straight();
  VehicleParams vp;
  Planner planner(pp, sc);
  Controller ctl(ControllerParams{}, vp, 0.05);
  Actuators act(vp, 0.04, 0.05, 0.9);
  VehicleState ego;
  ego.v = ego_v;
  double lead_x = lead_s;
  std::vector<Event> ev;
  Follow f;
  for (double t = 0; t < seconds; t += 0.05) {
    std::vector<PerceivedObject> objs{object_at({lead_x, 0}, {lead_v, 0})};
    const Plan& plan = planner.update(t, ego, objs, ev);
    auto cmd = ctl.update(ego, {&planner.active_path(), plan.lateral_offset, plan.accel, plan.v_ref(t)});
    act.apply(cmd.steer_cmd, cmd.accel_cmd, ego);
    step_vehicle(ego, vp, 0.05);
    lead_x += lead_v * 0.05;
    const double gap = lead_x - ego.pos.x - 0.5 * (vp.length + 4.6);
    f.min_gap = std::min(f.min_gap, gap);
    f.final_gap = gap;
  }
  f.final_v = ego.v;
  return f;
}

}  // namespace

TEST(Planner, StopsBehindStoppedCar) {
  Follow f = follow(PlannerParams{}, 15.0, 80.0, 0.0, 30.0);
  EXPECT_LT(f.final_v, 0.1);
  EXPECT_GT(f.min_gap, 2.0);
  EXPECT_LT(f.final_gap, 8.0);
}

TEST(Planner, FollowsSlowerLeadAtHeadway) {
  PlannerParams pp;
  Follow f = follow(pp, 18.0, 40.0, 10.0, 40.0);
  EXPECT_NEAR(f.final_v, 10.0, 0.3);
  const double expected = pp.min_gap_m + pp.headway_s * 10.0;
  EXPECT_NEAR(f.final_gap, expected, 4.0);
}

TEST(Planner, ShorterHeadwayFollowsCloser) {
  PlannerParams tight;
  tight.headway_s = 0.8;
  Follow a = follow(PlannerParams{}, 18.0, 40.0, 10.0, 40.0);
  Follow b = follow(tight, 18.0, 40.0, 10.0, 40.0);
  EXPECT_LT(b.final_gap, a.final_gap - 4.0);
}

TEST(Planner, PredictsCutIns) {
  std::vector<Event> ev;
  Scenario sc = straight();
  VehicleState ego;
  ego.v = 15;
  // in the next lane, drifting towards us at 1.2 m/s
  std::vector<PerceivedObject> objs{object_at({25, 3.0}, {12, -1.2})};
  PlannerParams on;
  Planner with(on, sc);
  EXPECT_EQ(with.update(0, ego, objs, ev).lead_id, 1);
  PlannerParams off;
  off.predict_cut_ins = false;
  Planner without(off, sc);
  EXPECT_EQ(without.update(0, ego, objs, ev).lead_id, -1);
}

TEST(Planner, YieldsToCrossingPedestrian) {
  std::vector<Event> ev;
  Scenario sc = straight(13.0);
  VehicleState ego;
  ego.v = 12;
  std::vector<PerceivedObject> objs{object_at({45, -4.5}, {0, 1.4}, ActorKind::Pedestrian)};
  Planner yield(PlannerParams{}, sc);
  const Plan p = yield.update(0, ego, objs, ev);
  EXPECT_EQ(p.lead_id, 1);
  EXPECT_LT(p.accel, 0.0);

  PlannerParams no_yield;
  no_yield.yield_to_crossing_peds = false;
  Planner late(no_yield, sc);
  EXPECT_EQ(late.update(0, ego, objs, ev).lead_id, -1);
}

TEST(Planner, IgnoresObjectsInOtherLanes) {
  std::vector<Event> ev;
  Scenario sc = straight();
  VehicleState ego;
  ego.v = 15;
  Planner planner(PlannerParams{}, sc);
  const Plan p = planner.update(0, ego, {object_at({30, 3.6}, {0, 0})}, ev);
  EXPECT_EQ(p.lead_id, -1);
  EXPECT_GT(p.accel, 0.0);
}

TEST(Planner, SlowsForCurves) {
  std::vector<Event> ev;
  Scenario sc;
  sc.family = "test";
  sc.route = PathBuilder().straight(100).arc(40, kPi / 2).straight(100).build();
  sc.map_route = sc.route;
  sc.default_limit = 25;
  Planner planner(PlannerParams{}, sc);
  VehicleState ego;
  ego.pos = sc.route.point_at(80);
  ego.v = 20;
  const Plan p = planner.update(0, ego, {}, ev);
  // sqrt(2.2 * 40) = 9.4 m/s in the bend, 20 m ahead
  EXPECT_LT(p.v_cap, 15.0);
  EXPECT_LT(p.accel, 0.0);
}

TEST(Planner, CurveOffsetKnobPushesOutward) {
  std::vector<Event> ev;
  Scenario sc;
  sc.family = "test";
  sc.route = PathBuilder().straight(50).arc(40, kPi / 2).straight(100).build();  // left turn
  sc.map_route = sc.route;
  PlannerParams pp;
  pp.curve_offset_m = 0.6;
  Planner planner(pp, sc);
  VehicleState ego;
  ego.pos = sc.route.point_at(60);
  ego.yaw = sc.route.heading_at(60);
  ego.v = 9;
  EXPECT_NEAR(planner.update(0, ego, {}, ev).lateral_offset, -0.6, 1e-9);  // right of a left bend
}

TEST(Planner, StaleMapFollowsPriorLane) {
  Scenario sc = make_scenario("construction_shift", 3);
  PlannerParams pp;
  pp.use_live_lane = false;
  Planner planner(pp, sc);
  EXPECT_EQ(&planner.active_path(), &sc.map_route);
  Planner live(PlannerParams{}, sc);
  EXPECT_EQ(&live.active_path(), &sc.route);
}

TEST(Planner, LatencyDelaysPlansAndCountsMisses) {
  Scenario sc = straight();
  sc.seed = 21;
  PlannerParams pp;
  pp.latency_jitter_ms = 0.0;
  pp.latency_per_object_ms = 0.0;
  pp.spike_prob = 0.0;
  pp.latency_mean_ms = 60.0;
  Planner planner(pp, sc);
  std::vector<Event> ev;
  VehicleState ego;
  ego.v = 5;
  planner.update(0.0, ego, {}, ev);
  ego.v = 10;
  // the cycle started at t=0 lands at t=0.06
  EXPECT_DOUBLE_EQ(planner.update(0.05, ego, {}, ev).v0, 5.0);
  EXPECT_EQ(planner.stats().cycles, 1);
  EXPECT_DOUBLE_EQ(planner.stats().last_latency_ms, 60.0);
  EXPECT_TRUE(ev.empty());

  PlannerParams slow = pp;
  slow.latency_mean_ms = 130.0;
  Planner late(slow, sc);
  for (int i = 0; i < 10; ++i) late.update(i * 0.05, ego, {}, ev);
  EXPECT_EQ(late.stats().deadline_misses, 5);
  EXPECT_EQ(late.stats().consecutive_misses, 5);
  ASSERT_FALSE(ev.empty());
  EXPECT_EQ(ev.front().kind, "latency_spike");
  EXPECT_EQ(ev.front().detail, "deadline_miss");
}

TEST(Planner, SpikesAreSharedAcrossBuilds) {
  // the same scenario seed gives the same spike times; a build with more
  // frequent spikes sees a superset of them
  Scenario sc = straight();
  sc.seed = 99;
  PlannerParams base;
  base.spike_prob = 0.05;
  PlannerParams worse = base;
  worse.spike_prob = 0.15;
  Planner a(base, sc), b(worse, sc);
  std::vector<Event> ea, eb;
  VehicleState ego;
  for (int i = 0; i < 2000; ++i) {
    a.update(i * 0.05, ego, {}, ea);
    b.update(i * 0.05, ego, {}, eb);
  }
  EXPECT_GT(b.stats().deadline_misses, a.stats().deadline_misses);
  for (const auto& e : ea) {
    if (e.detail != "deadline_miss") continue;
    bool found = false;
    for (const auto& f : eb) found |= f.t == e.t;
    EXPECT_TRUE(found) << e.t;
  }
}
