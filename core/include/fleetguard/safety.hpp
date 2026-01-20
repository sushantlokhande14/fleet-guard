#pragma once

#include <vector>

#include "fleetguard/actors.hpp"
#include "fleetguard/telemetry.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

// Nearest real object in front of ego and inside its swept corridor. This is
// ground truth: it is what a safety driver sees, not what perception reports.
struct Hazard {
  int id = -1;
  ActorKind kind = ActorKind::Vehicle;
  double gap = kInf;  // bumper-to-bumper distance
  double ttc = kInf;  // time to collision at current closing speed
};

Hazard nearest_in_path(const VehicleState& ego, const VehicleParams& vp, const std::vector<ActorState>& actors,
                       double lateral_margin = 0.2);

// Oriented bounding-box overlap (separating axis test).
bool collides(const VehicleState& ego, const VehicleParams& vp, const ActorState& a);

}  // namespace fg
