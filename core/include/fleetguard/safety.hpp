#pragma once

#include <vector>

#include "fleetguard/actors.hpp"
#include "fleetguard/telemetry.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

// Nearest real object ahead of ego in its lane. This is ground truth: what a
// safety driver sees, not what perception reports. "In lane" is measured in the
// route's Frenet frame so curves and lane shifts do not put roadside objects in
// a straight-ahead corridor.
struct Hazard {
  int id = -1;
  ActorKind kind = ActorKind::Vehicle;
  double gap = kInf;  // bumper-to-bumper distance along the route
  double ttc = kInf;  // time to collision at current closing speed
};

Hazard nearest_in_path(const Path& route, const Projection& ego_pr, const VehicleState& ego, const VehicleParams& vp,
                       const std::vector<ActorState>& actors, double lateral_margin = 0.2);

// Oriented bounding-box overlap (separating axis test).
bool collides(const VehicleState& ego, const VehicleParams& vp, const ActorState& a);

}  // namespace fg
