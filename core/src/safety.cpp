#include "fleetguard/safety.hpp"

#include <array>
#include <cmath>

namespace fg {

Hazard nearest_in_path(const VehicleState& ego, const VehicleParams& vp, const std::vector<ActorState>& actors,
                       double lateral_margin) {
  Hazard h;
  const Vec2 fwd = Vec2::from_angle(ego.yaw);
  const Vec2 left = fwd.perp();
  for (const auto& a : actors) {
    const Vec2 rel = a.pos - ego.pos;
    const double dx = rel.dot(fwd);
    const double dy = rel.dot(left);
    if (dx <= 0.0) continue;
    if (std::fabs(dy) > 0.5 * (vp.width + a.width) + lateral_margin) continue;
    const double gap = dx - 0.5 * (vp.length + a.length);
    if (gap >= h.gap) continue;
    h.id = a.id;
    h.kind = a.kind;
    h.gap = gap;
    const double closing = ego.v - a.vel.dot(fwd);
    h.ttc = (closing > 0.1 && gap > 0.0) ? gap / closing : (gap <= 0.0 ? 0.0 : kInf);
  }
  return h;
}

namespace {

std::array<Vec2, 4> corners(Vec2 c, double heading, double length, double width) {
  const Vec2 f = Vec2::from_angle(heading) * (0.5 * length);
  const Vec2 l = Vec2::from_angle(heading).perp() * (0.5 * width);
  return {c + f + l, c + f - l, c - f - l, c - f + l};
}

bool separated_on(Vec2 axis, const std::array<Vec2, 4>& a, const std::array<Vec2, 4>& b) {
  double amin = kInf, amax = -kInf, bmin = kInf, bmax = -kInf;
  for (const auto& p : a) {
    const double d = p.dot(axis);
    amin = std::min(amin, d);
    amax = std::max(amax, d);
  }
  for (const auto& p : b) {
    const double d = p.dot(axis);
    bmin = std::min(bmin, d);
    bmax = std::max(bmax, d);
  }
  return amax < bmin || bmax < amin;
}

}  // namespace

bool collides(const VehicleState& ego, const VehicleParams& vp, const ActorState& a) {
  // cheap reject first
  const double reach = 0.5 * (std::hypot(vp.length, vp.width) + std::hypot(a.length, a.width));
  if ((a.pos - ego.pos).norm2() > reach * reach) return false;
  const auto ce = corners(ego.pos, ego.yaw, vp.length, vp.width);
  const auto ca = corners(a.pos, a.heading, a.length, a.width);
  const Vec2 axes[4] = {Vec2::from_angle(ego.yaw), Vec2::from_angle(ego.yaw).perp(), Vec2::from_angle(a.heading),
                        Vec2::from_angle(a.heading).perp()};
  for (const auto& ax : axes) {
    if (separated_on(ax, ce, ca)) return false;
  }
  return true;
}

}  // namespace fg
