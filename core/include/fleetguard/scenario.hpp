#pragma once

#include <cstdint>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

#include "fleetguard/path.hpp"

namespace fg {

enum class Weather { Clear, Rain, Fog };
enum class ActorKind { Vehicle, Pedestrian, Cone };

const char* to_string(Weather w);
const char* to_string(ActorKind k);

// Actor applies `accel` for `duration` seconds starting at time `t`.
struct SpeedChange {
  double t = 0.0;
  double accel = 0.0;
  double duration = 0.0;
};

// Actors are scripted in the route's Frenet frame: arc length s along the ego
// route and a lateral offset (left positive). That keeps every family easy to
// describe and makes "is it in my lane" a cheap check.
struct ActorSpec {
  int id = 0;
  ActorKind kind = ActorKind::Vehicle;
  double s0 = 0.0;
  double lat0 = 0.0;
  double v0 = 0.0;
  double min_speed = 0.0;
  double max_speed = 40.0;
  std::vector<SpeedChange> speed_changes;
  // lateral manoeuvre (cut-in, lane change)
  double t_lat = -1.0;
  double lat1 = 0.0;
  double lat_duration = 0.0;
  // pedestrians walk across the road starting at t_walk
  double t_walk = -1.0;
  double walk_speed = 0.0;
  double length = 4.6;
  double width = 1.9;
};

struct SpeedZone {
  double s0, s1, limit;
};

struct Scenario {
  std::string family;
  uint64_t seed = 0;
  Path route;      // the drivable lane as it is today
  Path map_route;  // the lane in the prior map; differs from `route` in work zones
  std::vector<SpeedZone> zones;
  double default_limit = 13.9;
  double lane_width = 3.6;
  double ego_v0 = 10.0;
  Weather weather = Weather::Clear;
  double friction = 0.9;
  double time_limit = 60.0;
  std::vector<ActorSpec> actors;

  std::string id() const { return family + "-" + std::to_string(seed); }
  double speed_limit_at(double s) const;
  // compact parameter summary (stored with every drive, used in reports)
  nlohmann::json describe() const;
  // route + map geometry, downsampled, for replay views
  nlohmann::json geometry(double step = 2.0) const;
};

const std::vector<std::string>& scenario_families();
bool is_family(const std::string& name);

// Deterministic: the same (family, seed) always produces the same scenario.
Scenario make_scenario(const std::string& family, uint64_t seed);

}  // namespace fg
