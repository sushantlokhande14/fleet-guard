#include "fleetguard/perception.hpp"

#include <cmath>

namespace fg {

namespace {

constexpr double kRelevantRange = 60.0;  // m ahead along the route
constexpr double kCorridor = 2.2;        // m either side of the lane centre
constexpr double kMissEventRange = 35.0; // a miss this close is worth an event

}  // namespace

Perception::Perception(const PerceptionParams& p, const Scenario& sc, double dt)
    : p_(p),
      sc_(sc),
      dt_(dt),
      rng_(derive_seed(sc.seed, stream::kPerception)),
      phantom_rng_(derive_seed(sc.seed, stream::kPhantom)) {
  double scale = 1.0;
  weather_miss_ = 0.0;
  if (sc.weather == Weather::Rain) {
    scale = p.rain_range_scale;
    weather_miss_ = p.rain_miss_add;
  } else if (sc.weather == Weather::Fog) {
    scale = p.fog_range_scale;
    weather_miss_ = p.fog_miss_add;
  }
  range_eff_ = p.range_m * scale;
}

double Perception::miss_probability(const ActorState& a, double range) const {
  double pm = (a.kind == ActorKind::Pedestrian ? p_.ped_miss_rate : p_.vehicle_miss_rate) + weather_miss_;
  pm += p_.range_miss_slope * std::max(0.0, range - 30.0);
  if (a.kind == ActorKind::Pedestrian && range > p_.ped_far_range_m) pm += p_.ped_far_miss_add;
  return clamp(pm, 0.0, 0.99);
}

void Perception::update_track(Track& tr, Vec2 meas) {
  // alpha-beta filter
  constexpr double kAlpha = 0.5, kBeta = 0.1;
  const Vec2 pred = tr.pos + tr.vel * dt_;
  const Vec2 r = meas - pred;
  tr.pos = pred + r * kAlpha;
  tr.vel = tr.vel + r * (kBeta / dt_);
  tr.hits++;
  tr.misses = 0;
  if (tr.hits >= p_.confirm_frames) tr.confirmed = true;
}

const std::vector<PerceivedObject>& Perception::update(double t, const VehicleState& ego,
                                                       const std::vector<ActorState>& actors,
                                                       std::vector<Event>& events) {
  const Vec2 fwd = Vec2::from_angle(ego.yaw);
  const double half_fov = deg2rad(p_.fov_deg) * 0.5;

  // --- real objects ---------------------------------------------------------
  for (const auto& a : actors) {
    // fixed draw order per actor per tick, whatever the outcome
    const double u = rng_.uniform();
    const double nx = rng_.normal();
    const double ny = rng_.normal();
    const double nv = rng_.normal();

    const Vec2 rel = a.pos - ego.pos;
    const double range = rel.norm();
    const double bearing = std::fabs(wrap_angle(rel.angle() - ego.yaw));
    const bool visible = range <= range_eff_ && bearing <= half_fov;
    const bool detected = visible && u >= miss_probability(a, range);

    auto it = tracks_.find(a.id);
    if (detected) {
      const double sigma = p_.pos_noise_m + p_.pos_noise_per_m * range;
      const Vec2 meas = ego.pos + rel * p_.range_scale + Vec2{nx, ny} * sigma;
      if (it == tracks_.end()) {
        Track tr;
        tr.id = next_track_id_++;
        tr.truth_id = a.id;
        tr.kind = a.kind;
        tr.pos = meas;
        // radar-style initial velocity: true velocity plus noise
        tr.vel = a.vel + fwd * (0.5 * nv);
        tr.hits = 1;
        tr.confirmed = tr.hits >= p_.confirm_frames;
        tr.length = a.length;
        tr.width = a.width;
        tracks_.emplace(a.id, tr);
      } else {
        update_track(it->second, meas);
      }
    } else if (it != tracks_.end()) {
      Track& tr = it->second;
      tr.misses++;
      tr.pos = tr.pos + tr.vel * dt_;  // coast
      if (tr.misses > p_.coast_frames) tracks_.erase(it);
    }
  }

  // --- phantom detections (clutter, reflections) ----------------------------
  {
    const double u_spawn = phantom_rng_.uniform();
    const double u_range = phantom_rng_.uniform();
    const double u_lat = phantom_rng_.uniform();
    const double u_life = phantom_rng_.uniform();
    if (u_spawn < p_.fp_rate) {
      Track ph;
      ph.id = next_track_id_++;
      ph.truth_id = -1;
      ph.pos = ego.pos + fwd * lerp(12.0, 45.0, u_range) + fwd.perp() * lerp(-1.0, 1.0, u_lat);
      ph.vel = {0.0, 0.0};
      ph.life = 1 + static_cast<int>(u_life * std::max(1, p_.fp_max_frames));
      ph.length = 4.0;
      ph.width = 1.8;
      phantoms_.push_back(ph);
    }
    for (auto it = phantoms_.begin(); it != phantoms_.end();) {
      if (it->life > 0) {
        it->life--;
        it->hits++;
        it->misses = 0;
        if (it->hits >= p_.confirm_frames) it->confirmed = true;
      } else {
        it->misses++;
      }
      if (it->misses > p_.coast_frames) {
        it = phantoms_.erase(it);
      } else {
        ++it;
      }
    }
  }

  score(t, ego, actors, events);

  // --- publish through the latency pipeline ---------------------------------
  std::vector<PerceivedObject> snap;
  for (const auto& kv : tracks_) {
    const Track& tr = kv.second;
    if (!tr.confirmed) continue;
    snap.push_back({tr.id, tr.truth_id, tr.kind, tr.pos, tr.vel, tr.length, tr.width});
  }
  for (const auto& ph : phantoms_) {
    if (!ph.confirmed) continue;
    snap.push_back({ph.id, -1, ph.kind, ph.pos, ph.vel, ph.length, ph.width});
  }
  pipeline_.emplace_back(t + p_.latency_ms / 1000.0, std::move(snap));
  while (!pipeline_.empty() && pipeline_.front().first <= t + 1e-9) {
    output_ = std::move(pipeline_.front().second);
    pipeline_.pop_front();
  }
  return output_;
}

void Perception::score(double t, const VehicleState& ego, const std::vector<ActorState>& actors,
                       std::vector<Event>& events) {
  tick_ = {};
  const Projection ep = sc_.route.project(ego.pos, ego_hint_);
  ego_hint_ = ep.segment;
  for (const auto& a : actors) {
    if (a.kind == ActorKind::Cone) continue;  // infrastructure is scored separately, if at all
    const double ds = a.s - ep.s;
    const bool relevant = ds > 0.0 && ds <= kRelevantRange && std::fabs(a.lat) < kCorridor;
    auto tr = tracks_.find(a.id);
    const bool tracked = tr != tracks_.end() && tr->second.confirmed;
    if (relevant) {
      tick_.relevant++;
      if (tracked) {
        tick_.tracked++;
        tp_++;
      } else {
        tick_.missed++;
        fn_++;
      }
    }
    // close misses become events: object right in front of us and no track for 0.5 s
    const bool close_miss = relevant && !tracked && ds <= kMissEventRange;
    auto ep_it = miss_episodes_.find(a.id);
    if (ep_it == miss_episodes_.end()) {
      ep_it = miss_episodes_.emplace(a.id, EpisodeDetector("perception_miss", 2, 0.5, false)).first;
    }
    labels_[a.id] = std::string(to_string(a.kind)) + " " + std::to_string(a.id);
    const size_t before = events.size();
    ep_it->second.update(t, close_miss, ds, events);
    for (size_t i = before; i < events.size(); ++i) events[i].detail = labels_[a.id];
  }

  const Vec2 fwd = Vec2::from_angle(ego.yaw);
  double nearest_phantom = kInf;
  for (const auto& ph : phantoms_) {
    if (!ph.confirmed) continue;
    const Vec2 rel = ph.pos - ego.pos;
    const double dx = rel.dot(fwd), dy = rel.dot(fwd.perp());
    if (dx > 0 && dx <= kRelevantRange && std::fabs(dy) < kCorridor) {
      tick_.phantom++;
      fp_++;
      nearest_phantom = std::min(nearest_phantom, dx);
    }
  }
  phantom_episode_.update(t, tick_.phantom > 0, nearest_phantom, events);
}

void Perception::flush(double t, std::vector<Event>& events) {
  for (auto& kv : miss_episodes_) {
    const size_t before = events.size();
    kv.second.flush(t, events);
    for (size_t i = before; i < events.size(); ++i) events[i].detail = labels_[kv.first];
  }
  phantom_episode_.flush(t, events);
}

}  // namespace fg
