#pragma once

#include <vector>

#include "fleetguard/scenario.hpp"

namespace fg {

// Ground-truth state of one actor at the current tick.
struct ActorState {
  int id = 0;
  ActorKind kind = ActorKind::Vehicle;
  Vec2 pos;
  Vec2 vel;
  double heading = 0.0;
  double s = 0.0;    // along the ego route
  double lat = 0.0;  // from the ego route centre line
  double speed = 0.0;
  double length = 0.0;
  double width = 0.0;
};

// Steps scripted actors forward in time.
class ActorSim {
 public:
  explicit ActorSim(const Scenario& sc);

  void step(double t, double dt);
  const std::vector<ActorState>& states() const { return states_; }

 private:
  void place(size_t i, double lat_rate);

  const Scenario& sc_;
  std::vector<ActorState> states_;
};

}  // namespace fg
