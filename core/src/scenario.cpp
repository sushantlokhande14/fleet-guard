#include "fleetguard/scenario.hpp"

#include <algorithm>
#include <functional>
#include <map>
#include <stdexcept>

#include "fleetguard/rng.hpp"

namespace fg {

const char* to_string(Weather w) {
  switch (w) {
    case Weather::Clear: return "clear";
    case Weather::Rain: return "rain";
    case Weather::Fog: return "fog";
  }
  return "?";
}

const char* to_string(ActorKind k) {
  switch (k) {
    case ActorKind::Vehicle: return "vehicle";
    case ActorKind::Pedestrian: return "pedestrian";
    case ActorKind::Cone: return "cone";
  }
  return "?";
}

double Scenario::speed_limit_at(double s) const {
  double lim = default_limit;
  for (const auto& z : zones) {
    if (s >= z.s0 && s <= z.s1) lim = std::min(lim, z.limit);
  }
  return lim;
}

nlohmann::json Scenario::describe() const {
  nlohmann::json j;
  j["id"] = id();
  j["family"] = family;
  j["seed"] = seed;
  j["route_length_m"] = route.length();
  j["speed_limit_mps"] = default_limit;
  j["ego_v0_mps"] = ego_v0;
  j["weather"] = to_string(weather);
  j["friction"] = friction;
  j["time_limit_s"] = time_limit;
  j["zones"] = nlohmann::json::array();
  for (const auto& z : zones) j["zones"].push_back({{"s0", z.s0}, {"s1", z.s1}, {"limit", z.limit}});
  int cones = 0;
  j["actors"] = nlohmann::json::array();
  for (const auto& a : actors) {
    if (a.kind == ActorKind::Cone) {
      ++cones;
      continue;
    }
    nlohmann::json aj{{"id", a.id}, {"kind", to_string(a.kind)}, {"s0", a.s0}, {"lat0", a.lat0}, {"v0", a.v0}};
    if (a.t_lat >= 0) aj["cut_in"] = {{"t", a.t_lat}, {"to_lat", a.lat1}, {"duration", a.lat_duration}};
    if (a.t_walk >= 0) aj["walk"] = {{"t", a.t_walk}, {"speed", a.walk_speed}};
    if (!a.speed_changes.empty()) {
      aj["speed_changes"] = nlohmann::json::array();
      for (const auto& c : a.speed_changes)
        aj["speed_changes"].push_back({{"t", c.t}, {"accel", c.accel}, {"duration", c.duration}});
    }
    j["actors"].push_back(aj);
  }
  j["cones"] = cones;
  return j;
}

nlohmann::json Scenario::geometry(double step) const {
  auto sample = [step](const Path& p) {
    nlohmann::json pts = nlohmann::json::array();
    for (double s = 0; s < p.length(); s += step) {
      const Vec2 q = p.point_at(s);
      pts.push_back({q.x, q.y});
    }
    const Vec2 e = p.points().back();
    pts.push_back({e.x, e.y});
    return pts;
  };
  nlohmann::json j;
  j["route"] = sample(route);
  if (map_route.points() != route.points()) j["map_route"] = sample(map_route);
  j["lane_width"] = lane_width;
  return j;
}

namespace {

constexpr double kLane = 3.6;

double random_sign(Rng& r) { return r.bernoulli(0.5) ? 1.0 : -1.0; }

void pick_weather(Scenario& sc, Rng& r) {
  const double u = r.uniform();
  if (u < 0.70) {
    sc.weather = Weather::Clear;
    sc.friction = r.uniform(0.85, 0.95);
  } else if (u < 0.90) {
    sc.weather = Weather::Rain;
    sc.friction = r.uniform(0.55, 0.70);
  } else {
    sc.weather = Weather::Fog;
    sc.friction = r.uniform(0.80, 0.90);
  }
}

void finish(Scenario& sc, double nominal_speed, double slack = 20.0) {
  if (sc.map_route.empty()) sc.map_route = sc.route;
  sc.time_limit = sc.route.length() / (0.7 * nominal_speed) + slack;
}

ActorSpec vehicle(int id, double s0, double lat0, double v0) {
  ActorSpec a;
  a.id = id;
  a.kind = ActorKind::Vehicle;
  a.s0 = s0;
  a.lat0 = a.lat1 = lat0;
  a.v0 = v0;
  return a;
}

// Highway car following; the lead brakes hard once.
Scenario highway_follow(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(26.0, 31.0);
  sc.route = PathBuilder()
                 .straight(r.uniform(150, 250))
                 .arc(r.uniform(500, 900), random_sign(r) * deg2rad(r.uniform(8, 20)))
                 .straight(r.uniform(250, 400))
                 .build();
  sc.ego_v0 = sc.default_limit * 0.92;
  ActorSpec lead = vehicle(1, r.uniform(45, 70), 0.0, sc.default_limit * r.uniform(0.78, 0.92));
  const double t_brake = r.uniform(7, 16);
  const double brake_dur = r.uniform(1.5, 3.0);
  lead.speed_changes.push_back({t_brake, -r.uniform(3.0, 6.5), brake_dur});
  lead.speed_changes.push_back({t_brake + brake_dur + 2.0, 1.2, 4.0});
  lead.max_speed = sc.default_limit;
  sc.actors.push_back(lead);
  pick_weather(sc, r);
  finish(sc, sc.default_limit);
  return sc;
}

// A slower car in the next lane cuts in ahead of ego.
Scenario urban_cut_in(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(12.5, 16.0);
  sc.route = PathBuilder()
                 .straight(r.uniform(120, 200))
                 .arc(r.uniform(150, 300), random_sign(r) * deg2rad(r.uniform(5, 15)))
                 .straight(r.uniform(150, 250))
                 .build();
  sc.ego_v0 = sc.default_limit * 0.95;
  const double side = random_sign(r);
  ActorSpec cut = vehicle(1, r.uniform(12, 35), side * kLane, sc.ego_v0 * r.uniform(0.70, 0.92));
  cut.t_lat = r.uniform(2.5, 6.0);
  cut.lat_duration = r.uniform(2.0, 3.5);
  cut.lat1 = 0.0;
  if (r.bernoulli(0.5)) cut.speed_changes.push_back({cut.t_lat + cut.lat_duration, 1.0, 3.0});
  cut.max_speed = sc.default_limit;
  sc.actors.push_back(cut);
  pick_weather(sc, r);
  finish(sc, sc.default_limit);
  return sc;
}

// Pedestrian crosses ahead; timing is drawn around ego's arrival so some
// crossings need a yield and some clear before ego gets there.
Scenario ped_crossing(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(11.0, 14.0);
  sc.route = PathBuilder().straight(r.uniform(220, 320)).build();
  sc.ego_v0 = sc.default_limit * 0.95;
  const int n = r.bernoulli(0.3) ? 2 : 1;
  double s = r.uniform(80, 150);
  for (int i = 0; i < n; ++i) {
    ActorSpec p;
    p.id = i + 1;
    p.kind = ActorKind::Pedestrian;
    p.s0 = s;
    p.lat0 = random_sign(r) * r.uniform(4.5, 7.0);
    p.walk_speed = r.uniform(1.1, 1.8);
    const double arrival = s / sc.ego_v0;
    p.t_walk = std::max(0.5, arrival - std::fabs(p.lat0) / p.walk_speed + r.uniform(-3.0, 1.0));
    p.length = p.width = 0.6;
    sc.actors.push_back(p);
    s += r.uniform(40, 80);
  }
  pick_weather(sc, r);
  finish(sc, sc.default_limit, 30.0);
  return sc;
}

// Alternating curves; exercises lateral control.
Scenario s_curve(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(15.0, 22.0);
  PathBuilder b;
  b.straight(60);
  double side = random_sign(r);
  const int n = r.uniform_int(4, 6);
  for (int k = 0; k < n; ++k) {
    b.arc(r.uniform(35, 110), side * deg2rad(r.uniform(20, 50)));
    b.straight(r.uniform(10, 40));
    side = -side;
  }
  b.straight(80);
  sc.route = b.build();
  sc.ego_v0 = sc.default_limit * 0.8;
  if (r.bernoulli(0.4)) {
    ActorSpec lead = vehicle(1, r.uniform(30, 50), 0.0, sc.default_limit * 0.8);
    lead.max_speed = sc.default_limit * 0.85;
    sc.actors.push_back(lead);
  }
  pick_weather(sc, r);
  finish(sc, sc.default_limit * 0.8);
  return sc;
}

// 90 degree turn at an intersection, sometimes behind another car.
Scenario intersection_turn(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(11.0, 14.0);
  sc.route = PathBuilder()
                 .straight(r.uniform(60, 110))
                 .arc(r.uniform(11, 20), random_sign(r) * kPi / 2)
                 .straight(r.uniform(120, 200))
                 .build();
  sc.ego_v0 = sc.default_limit * 0.9;
  if (r.bernoulli(0.5)) {
    ActorSpec lead = vehicle(1, r.uniform(25, 40), 0.0, sc.ego_v0 * 0.85);
    lead.speed_changes.push_back({r.uniform(2.0, 5.0), -1.5, 2.5});
    lead.speed_changes.push_back({9.0, 1.0, 4.0});
    lead.min_speed = 3.0;
    lead.max_speed = sc.default_limit * 0.9;
    sc.actors.push_back(lead);
  }
  pick_weather(sc, r);
  finish(sc, sc.default_limit * 0.75);
  return sc;
}

// Work zone: the live lane is shifted sideways while the prior map still has the
// old alignment, and cones sit on the old lane centre.
Scenario construction_shift(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(20.0, 25.0);
  const double a = r.uniform(150, 220);
  const double shift_len = r.uniform(30, 45);
  const double zone_len = r.uniform(60, 120);
  const double back_len = r.uniform(30, 45);
  const double tail = r.uniform(100, 180);
  const double shift = random_sign(r) * r.uniform(2.8, 3.4);

  sc.route = PathBuilder().straight(a).lane_shift(shift_len, shift).straight(zone_len).lane_shift(back_len, -shift).straight(tail).build();
  sc.map_route = PathBuilder().straight(a + shift_len + zone_len + back_len + tail).build();

  const double zone_limit = r.uniform(11.0, 14.0);
  sc.zones.push_back({a - 60.0, a + shift_len + zone_len + back_len + 20.0, zone_limit});

  // cones along the closed lane wherever it is displaced from the live lane
  int id = 1;
  for (double x = a + 8.0; x < a + shift_len + zone_len + back_len - 8.0; x += 8.0) {
    const Projection pr = sc.route.project(sc.map_route.point_at(x));
    if (std::fabs(pr.lateral) < 1.6) continue;
    ActorSpec c;
    c.id = id++;
    c.kind = ActorKind::Cone;
    c.s0 = pr.s;
    c.lat0 = c.lat1 = pr.lateral;
    c.length = c.width = 0.4;
    c.max_speed = 0.0;
    sc.actors.push_back(c);
  }
  sc.ego_v0 = sc.default_limit * 0.9;
  pick_weather(sc, r);
  finish(sc, zone_limit);
  return sc;
}

// Dense traffic: the lead repeatedly brakes, sometimes to a stop, and pulls away.
Scenario stop_and_go(Rng& r) {
  Scenario sc;
  sc.default_limit = r.uniform(14.0, 19.0);
  sc.route = PathBuilder()
                 .straight(r.uniform(200, 300))
                 .arc(r.uniform(200, 400), random_sign(r) * deg2rad(r.uniform(5, 15)))
                 .straight(r.uniform(150, 250))
                 .build();
  sc.ego_v0 = r.uniform(6.0, 10.0);
  ActorSpec lead = vehicle(1, r.uniform(18, 30), 0.0, sc.ego_v0);
  double t = r.uniform(3.0, 6.0);
  const int cycles = r.uniform_int(4, 6);
  for (int k = 0; k < cycles; ++k) {
    const double brake = r.uniform(1.5, 3.0);
    lead.speed_changes.push_back({t, -r.uniform(2.0, 4.5), brake});
    t += brake + r.uniform(1.0, 3.0);
    const double go = r.uniform(2.0, 4.0);
    lead.speed_changes.push_back({t, r.uniform(1.0, 2.0), go});
    t += go + r.uniform(1.0, 3.0);
  }
  lead.max_speed = sc.default_limit * 0.9;
  sc.actors.push_back(lead);
  pick_weather(sc, r);
  finish(sc, sc.default_limit * 0.5, 30.0);
  return sc;
}

using Generator = std::function<Scenario(Rng&)>;

const std::map<std::string, Generator>& generators() {
  static const std::map<std::string, Generator> g = {
      {"highway_follow", highway_follow},
      {"urban_cut_in", urban_cut_in},
      {"ped_crossing", ped_crossing},
      {"s_curve", s_curve},
      {"intersection_turn", intersection_turn},
      {"construction_shift", construction_shift},
      {"stop_and_go", stop_and_go},
  };
  return g;
}

}  // namespace

const std::vector<std::string>& scenario_families() {
  static const std::vector<std::string> names = [] {
    std::vector<std::string> v;
    for (const auto& kv : generators()) v.push_back(kv.first);
    return v;
  }();
  return names;
}

bool is_family(const std::string& name) { return generators().count(name) > 0; }

Scenario make_scenario(const std::string& family, uint64_t seed) {
  auto it = generators().find(family);
  if (it == generators().end()) throw std::invalid_argument("unknown scenario family: " + family);
  Rng r(derive_seed(seed, stream::kScenario));
  Scenario sc = it->second(r);
  sc.family = family;
  sc.seed = seed;
  sc.lane_width = kLane;
  return sc;
}

}  // namespace fg
