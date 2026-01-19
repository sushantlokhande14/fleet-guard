#pragma once

#include "fleetguard/build_config.hpp"
#include "fleetguard/scenario.hpp"
#include "fleetguard/telemetry.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

// Output of one planning cycle. Control integrates `accel` from the speed at
// planning time to get its speed reference until the next plan lands.
struct Plan {
  double t_plan = 0.0;
  double v0 = 0.0;
  double accel = 0.0;
  double v_cap = 0.0;  // free-road target speed
  double lateral_offset = 0.0;
  bool use_map = false;
  int lead_id = -1;
  double lead_gap = kInf;

  double v_ref(double t) const {
    const double v = v0 + accel * (t - t_plan);
    if (accel >= 0.0) return std::min(v, std::max(v_cap, v0));
    return std::max(v, 0.0);
  }
};

class Planner {
 public:
  Planner(const PlannerParams& p, const Scenario& sc);

  // Runs a cycle when one is due; returns the plan control should use now.
  const Plan& update(double t, const VehicleState& ego);

  const Path& active_path() const { return p_.use_live_lane ? sc_.route : sc_.map_route; }

 private:
  Plan compute(double t, const VehicleState& ego);
  double free_road_target(double s, double v) const;

  PlannerParams p_;
  const Scenario& sc_;
  Plan current_;
  double next_cycle_ = 0.0;
  size_t hint_ = Path::npos;
};

}  // namespace fg
