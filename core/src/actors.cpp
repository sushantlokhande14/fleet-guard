#include "fleetguard/actors.hpp"

#include <cmath>

namespace fg {

ActorSim::ActorSim(const Scenario& sc) : sc_(sc) {
  states_.reserve(sc.actors.size());
  for (const auto& a : sc.actors) {
    ActorState st;
    st.id = a.id;
    st.kind = a.kind;
    st.s = a.s0;
    st.lat = a.lat0;
    st.speed = a.v0;
    st.length = a.length;
    st.width = a.width;
    states_.push_back(st);
  }
  for (size_t i = 0; i < states_.size(); ++i) place(i, 0.0);
}

void ActorSim::place(size_t i, double lat_rate) {
  ActorState& st = states_[i];
  const Vec2 tangent = sc_.route.tangent_at(st.s);
  const Vec2 normal = tangent.perp();
  st.pos = sc_.route.point_at(st.s) + normal * st.lat;
  st.vel = tangent * st.speed + normal * lat_rate;
  st.heading = st.kind == ActorKind::Vehicle ? std::atan2(st.vel.y, st.vel.x) : sc_.route.heading_at(st.s);
  if (st.kind == ActorKind::Vehicle && st.speed < 0.1 && std::fabs(lat_rate) < 0.1) st.heading = tangent.angle();
}

void ActorSim::step(double t, double dt) {
  for (size_t i = 0; i < states_.size(); ++i) {
    const ActorSpec& spec = sc_.actors[i];
    ActorState& st = states_[i];
    if (spec.kind == ActorKind::Cone) continue;

    // longitudinal: sum of active scripted accelerations
    double accel = 0.0;
    for (const auto& c : spec.speed_changes) {
      if (t >= c.t && t < c.t + c.duration) accel += c.accel;
    }
    st.speed = clamp(st.speed + accel * dt, spec.min_speed, spec.max_speed);
    st.s += st.speed * dt;

    // lateral: smooth cut-in / lane change, or a pedestrian walking across
    double lat_rate = 0.0;
    if (spec.t_lat >= 0.0 && t >= spec.t_lat) {
      const double u = clamp((t - spec.t_lat) / spec.lat_duration, 0.0, 1.0);
      const double lat = spec.lat0 + (spec.lat1 - spec.lat0) * 0.5 * (1.0 - std::cos(kPi * u));
      lat_rate = (lat - st.lat) / dt;
      st.lat = lat;
    }
    if (spec.t_walk >= 0.0 && t >= spec.t_walk) {
      const double dir = spec.lat0 > 0 ? -1.0 : 1.0;
      // keep walking until well clear of the far side
      if (std::fabs(st.lat) < std::fabs(spec.lat0) + 0.5 || st.lat * spec.lat0 > 0) {
        lat_rate = dir * spec.walk_speed;
        st.lat += lat_rate * dt;
      }
    }
    place(i, lat_rate);
  }
}

}  // namespace fg
