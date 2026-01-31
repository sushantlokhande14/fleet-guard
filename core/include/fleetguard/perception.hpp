#pragma once

#include <deque>
#include <map>
#include <string>
#include <vector>

#include "fleetguard/actors.hpp"
#include "fleetguard/build_config.hpp"
#include "fleetguard/events.hpp"
#include "fleetguard/rng.hpp"
#include "fleetguard/vehicle.hpp"

namespace fg {

struct PerceivedObject {
  int track_id = 0;
  int truth_id = -1;  // -1: phantom, nothing real behind it
  ActorKind kind = ActorKind::Vehicle;
  Vec2 pos;
  Vec2 vel;
  double length = 0.0;
  double width = 0.0;
};

// Ground-truth scoring of the tracker for one tick.
struct PerceptionTickStats {
  int relevant = 0;  // real objects in the ego corridor within 60 m
  int tracked = 0;   // ... of which have a confirmed track
  int missed = 0;
  int phantom = 0;   // confirmed tracks in the corridor with nothing real behind them
};

// Sensor + tracker model. Detection, noise and phantom draws come from streams
// seeded by the scenario only and are consumed in a fixed order every tick, so
// two builds driving the same scenario see the same luck (common random numbers).
// A build with a higher miss rate misses a superset of what the baseline misses.
class Perception {
 public:
  Perception(const PerceptionParams& p, const Scenario& sc, double dt);

  // Sense the world at time t; returns what planning sees now, which is the
  // track list produced latency_ms ago.
  const std::vector<PerceivedObject>& update(double t, const VehicleState& ego, const std::vector<ActorState>& actors,
                                             std::vector<Event>& events);

  const PerceptionTickStats& tick_stats() const { return tick_; }
  int total_tp() const { return tp_; }
  int total_fn() const { return fn_; }
  int total_fp() const { return fp_; }
  void flush(double t, std::vector<Event>& events);

 private:
  struct Track {
    int id = 0;
    int truth_id = -1;
    ActorKind kind = ActorKind::Vehicle;
    int hits = 0;
    int misses = 0;
    bool confirmed = false;
    int life = 0;  // phantoms: frames of fake detections left
    Vec2 pos, vel;
    double length = 0.0, width = 0.0;
  };

  double miss_probability(const ActorState& a, double range) const;
  void update_track(Track& tr, Vec2 meas);
  void score(double t, const VehicleState& ego, const std::vector<ActorState>& actors, std::vector<Event>& events);

  PerceptionParams p_;
  const Scenario& sc_;
  double dt_;
  double range_eff_;
  double weather_miss_;
  Rng rng_;
  Rng phantom_rng_;
  int next_track_id_ = 1;
  std::map<int, Track> tracks_;  // by truth id
  std::vector<Track> phantoms_;
  std::deque<std::pair<double, std::vector<PerceivedObject>>> pipeline_;
  std::vector<PerceivedObject> output_;
  PerceptionTickStats tick_;
  int tp_ = 0, fn_ = 0, fp_ = 0;
  size_t ego_hint_ = Path::npos;
  std::map<int, EpisodeDetector> miss_episodes_;
  std::map<int, std::string> labels_;
  EpisodeDetector phantom_episode_{"phantom_object", 2, 0.0, false};
};

}  // namespace fg
