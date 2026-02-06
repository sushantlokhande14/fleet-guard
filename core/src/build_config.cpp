#include "fleetguard/build_config.hpp"

#include <functional>
#include <map>
#include <stdexcept>

namespace fg {

namespace {

template <class V>
void visit(PerceptionParams& p, V&& v) {
  v("range_m", p.range_m);
  v("fov_deg", p.fov_deg);
  v("vehicle_miss_rate", p.vehicle_miss_rate);
  v("ped_miss_rate", p.ped_miss_rate);
  v("range_miss_slope", p.range_miss_slope);
  v("ped_far_miss_add", p.ped_far_miss_add);
  v("ped_far_range_m", p.ped_far_range_m);
  v("rain_range_scale", p.rain_range_scale);
  v("fog_range_scale", p.fog_range_scale);
  v("rain_miss_add", p.rain_miss_add);
  v("fog_miss_add", p.fog_miss_add);
  v("pos_noise_m", p.pos_noise_m);
  v("pos_noise_per_m", p.pos_noise_per_m);
  v("range_scale", p.range_scale);
  v("fp_rate", p.fp_rate);
  v("fp_max_frames", p.fp_max_frames);
  v("latency_ms", p.latency_ms);
  v("confirm_frames", p.confirm_frames);
  v("coast_frames", p.coast_frames);
}

template <class V>
void visit(PlannerParams& p, V&& v) {
  v("cycle_ms", p.cycle_ms);
  v("latency_mean_ms", p.latency_mean_ms);
  v("latency_jitter_ms", p.latency_jitter_ms);
  v("latency_per_object_ms", p.latency_per_object_ms);
  v("spike_prob", p.spike_prob);
  v("spike_ms", p.spike_ms);
  v("watchdog_misses", p.watchdog_misses);
  v("headway_s", p.headway_s);
  v("min_gap_m", p.min_gap_m);
  v("max_accel", p.max_accel);
  v("comfort_decel", p.comfort_decel);
  v("max_decel", p.max_decel);
  v("speed_gain", p.speed_gain);
  v("lat_accel_max", p.lat_accel_max);
  v("lateral_margin_m", p.lateral_margin_m);
  v("predict_cut_ins", p.predict_cut_ins);
  v("cut_in_horizon_s", p.cut_in_horizon_s);
  v("yield_to_crossing_peds", p.yield_to_crossing_peds);
  v("ped_horizon_s", p.ped_horizon_s);
  v("use_live_lane", p.use_live_lane);
  v("curve_offset_m", p.curve_offset_m);
  v("curve_offset_kappa", p.curve_offset_kappa);
  v("lateral_bias_m", p.lateral_bias_m);
}

template <class V>
void visit(ControllerParams& p, V&& v) {
  v("lookahead_gain", p.lookahead_gain);
  v("lookahead_min", p.lookahead_min);
  v("steer_gain", p.steer_gain);
  v("speed_kp", p.speed_kp);
  v("speed_ki", p.speed_ki);
  v("integral_limit", p.integral_limit);
  v("jerk_limit", p.jerk_limit);
  v("actuator_delay_ms", p.actuator_delay_ms);
}

using Setter = std::function<void(const nlohmann::json&)>;

struct SetterCollector {
  std::map<std::string, Setter>& out;
  void operator()(const char* k, double& x) { out[k] = [&x](const nlohmann::json& j) { x = j.get<double>(); }; }
  void operator()(const char* k, int& x) { out[k] = [&x](const nlohmann::json& j) { x = j.get<int>(); }; }
  void operator()(const char* k, bool& x) { out[k] = [&x](const nlohmann::json& j) { x = j.get<bool>(); }; }
};

struct Writer {
  nlohmann::json& out;
  template <class T>
  void operator()(const char* k, T& x) {
    out[k] = x;
  }
};

template <class P>
void apply_section(P& params, const nlohmann::json& section, const std::string& name) {
  if (!section.is_object()) throw std::invalid_argument("build section '" + name + "' must be an object");
  std::map<std::string, Setter> setters;
  visit(params, SetterCollector{setters});
  for (auto it = section.begin(); it != section.end(); ++it) {
    auto s = setters.find(it.key());
    if (s == setters.end()) throw std::invalid_argument("unknown build parameter: " + name + "." + it.key());
    try {
      s->second(it.value());
    } catch (const nlohmann::json::exception&) {
      throw std::invalid_argument("bad value for build parameter: " + name + "." + it.key());
    }
  }
}

template <class P>
nlohmann::json write_section(P params) {
  nlohmann::json j = nlohmann::json::object();
  visit(params, Writer{j});
  return j;
}

}  // namespace

BuildConfig build_from_json(const nlohmann::json& j) {
  BuildConfig b;
  if (!j.is_object()) throw std::invalid_argument("build config must be a JSON object");
  for (auto it = j.begin(); it != j.end(); ++it) {
    const std::string& key = it.key();
    if (key == "name") {
      b.name = it.value().get<std::string>();
    } else if (key == "perception") {
      apply_section(b.perception, it.value(), key);
    } else if (key == "planner") {
      apply_section(b.planner, it.value(), key);
    } else if (key == "control") {
      apply_section(b.control, it.value(), key);
    } else if (key == "description" || key == "parent") {
      // informational, carried by the Python registry
    } else {
      throw std::invalid_argument("unknown build section: " + key);
    }
  }
  return b;
}

nlohmann::json build_to_json(const BuildConfig& b) {
  return {{"name", b.name},
          {"perception", write_section(b.perception)},
          {"planner", write_section(b.planner)},
          {"control", write_section(b.control)}};
}

}  // namespace fg
