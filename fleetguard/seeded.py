"""Seeded regression catalog.

Each case is a deliberate, realistic bug injected into the baseline build, with
the category a triage engineer would file it under. Five mechanisms per category,
each at a moderate and a severe magnitude, plus clean controls (no-op changes,
benign tunings and outright improvements) that must not be flagged.

The magnitudes were chosen from what the change means for the stack, not tuned
to be caught: several moderate cases are expected to slip through.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeededCase:
    id: str
    category: str  # expected category, or "clean" for controls
    level: str     # moderate | severe | control
    mechanism: str
    overrides: dict


def _pair(cat: str, key: str, mechanism: str, moderate: dict, severe: dict) -> list[SeededCase]:
    return [SeededCase(f"{cat}.{key}.moderate", cat, "moderate", mechanism, moderate),
            SeededCase(f"{cat}.{key}.severe", cat, "severe", mechanism, severe)]


CASES: list[SeededCase] = [
    # --- perception ------------------------------------------------------------
    *_pair("perception_error", "far_pedestrians", "pedestrian detector loses recall beyond 20 m",
           {"perception": {"ped_far_miss_add": 0.6, "ped_far_range_m": 20}},
           {"perception": {"ped_far_miss_add": 0.95, "ped_far_range_m": 20}}),
    *_pair("perception_error", "weather_range", "camera exposure change shortens range in rain and fog",
           {"perception": {"rain_range_scale": 0.6, "fog_range_scale": 0.4}},
           {"perception": {"rain_range_scale": 0.45, "fog_range_scale": 0.3}}),
    *_pair("perception_error", "phantoms", "radar clutter filter regression adds ghost objects",
           {"perception": {"fp_rate": 0.004, "fp_max_frames": 4}},
           {"perception": {"fp_rate": 0.01, "fp_max_frames": 6}}),
    *_pair("perception_error", "range_calibration", "lidar extrinsics overestimate range",
           {"perception": {"range_scale": 1.08}},
           {"perception": {"range_scale": 1.2}}),
    *_pair("perception_error", "slow_confirmation", "tracker needs more hits before publishing a track",
           {"perception": {"confirm_frames": 5}},
           {"perception": {"confirm_frames": 9}}),
    # --- latency -----------------------------------------------------------------
    *_pair("latency_spike", "spike_rate", "GC pauses in the planning process",
           {"planner": {"spike_prob": 0.012}},
           {"planner": {"spike_prob": 0.04}}),
    *_pair("latency_spike", "spike_size", "lock contention makes rare stalls longer",
           {"planner": {"spike_ms": 180}},
           {"planner": {"spike_ms": 300}}),
    *_pair("latency_spike", "per_object", "fusion work moved onto the planning thread",
           {"planner": {"latency_per_object_ms": 2.5}},
           {"planner": {"latency_per_object_ms": 4.5}}),
    *_pair("latency_spike", "mean_creep", "new cost terms slow every cycle",
           {"planner": {"latency_mean_ms": 55}},
           {"planner": {"latency_mean_ms": 72}}),
    *_pair("latency_spike", "jitter", "planner shares a core with logging",
           {"planner": {"latency_jitter_ms": 15}},
           {"planner": {"latency_jitter_ms": 25}}),
    # --- route -------------------------------------------------------------------
    *_pair("route_deviation", "curve_offset", "map curvature bug shifts the path outward on bends",
           {"planner": {"curve_offset_m": 0.4}},
           {"planner": {"curve_offset_m": 0.8}}),
    *_pair("route_deviation", "lateral_bias", "IMU mounting offset biases lane centring",
           {"planner": {"lateral_bias_m": 0.3}},
           {"planner": {"lateral_bias_m": 0.6}}),
    *_pair("route_deviation", "corner_cutting", "lookahead retune cuts corners",
           {"control": {"lookahead_gain": 1.0}},
           {"control": {"lookahead_gain": 1.6}}),
    *_pair("route_deviation", "gentle_curve_offset", "curvature bug also fires on gentle bends",
           {"planner": {"curve_offset_m": 0.3, "curve_offset_kappa": 0.004}},
           {"planner": {"curve_offset_m": 0.6, "curve_offset_kappa": 0.004}}),
    SeededCase("route_deviation.stale_map.severe", "route_deviation", "severe",
               "live lane updates disabled: follows the prior map through work zones",
               {"planner": {"use_live_lane": False}}),
    SeededCase("route_deviation.lateral_bias.subtle", "route_deviation", "moderate",
               "small calibration offset", {"planner": {"lateral_bias_m": 0.15}}),
    # --- control -----------------------------------------------------------------
    *_pair("control_instability", "steer_gain", "steering gain retuned on the test track",
           {"control": {"steer_gain": 1.35}},
           {"control": {"steer_gain": 1.8}}),
    *_pair("control_instability", "actuator_delay", "CAN gateway firmware adds latency",
           {"control": {"actuator_delay_ms": 110}},
           {"control": {"actuator_delay_ms": 170}}),
    *_pair("control_instability", "short_lookahead", "lookahead shortened for tighter tracking",
           {"control": {"lookahead_gain": 0.35}},
           {"control": {"lookahead_gain": 0.2}}),
    *_pair("control_instability", "speed_gain", "speed loop made more aggressive",
           {"control": {"speed_kp": 3.0}},
           {"control": {"speed_kp": 6.0}}),
    *_pair("control_instability", "integral", "speed integral gain raised, windup",
           {"control": {"speed_ki": 0.6}},
           {"control": {"speed_ki": 1.5}}),
    # --- planning (shows up as disengagements) -----------------------------------
    *_pair("disengagement", "headway", "following distance shortened",
           {"planner": {"headway_s": 1.0}},
           {"planner": {"headway_s": 0.7, "min_gap_m": 2.0}}),
    *_pair("disengagement", "ped_yield", "crossing-pedestrian prediction shortened or removed",
           {"planner": {"ped_horizon_s": 1.5}},
           {"planner": {"yield_to_crossing_peds": False}}),
    *_pair("disengagement", "cut_in", "cut-in prediction shortened or removed",
           {"planner": {"cut_in_horizon_s": 0.8}},
           {"planner": {"predict_cut_ins": False}}),
    *_pair("disengagement", "brake_cap", "planner deceleration capped",
           {"planner": {"max_decel": 4.5}},
           {"planner": {"max_decel": 3.0}}),
    *_pair("disengagement", "watchdog", "watchdog tolerance tightened",
           {"planner": {"watchdog_misses": 2}},
           {"planner": {"watchdog_misses": 1}}),
]

CONTROLS: list[SeededCase] = [
    SeededCase("clean.identical", "clean", "control", "version bump, no parameter change", {}),
    SeededCase("clean.max_accel", "clean", "control", "slightly stronger launch",
               {"planner": {"max_accel": 1.9}}),
    SeededCase("clean.comfort_decel", "clean", "control", "comfort decel 2.5 -> 2.6",
               {"planner": {"comfort_decel": 2.6}}),
    SeededCase("clean.perception_latency", "clean", "control", "+2 ms sensor latency",
               {"perception": {"latency_ms": 62}}),
    SeededCase("clean.position_noise", "clean", "control", "noise sigma 0.12 -> 0.13 m",
               {"perception": {"pos_noise_m": 0.13}}),
    SeededCase("clean.planner_mean", "clean", "control", "+1 ms planner mean",
               {"planner": {"latency_mean_ms": 33}}),
    SeededCase("clean.lookahead_min", "clean", "control", "lookahead floor 6.0 -> 6.5 m",
               {"control": {"lookahead_min": 6.5}}),
    SeededCase("clean.jerk_limit", "clean", "control", "jerk limit 12 -> 11",
               {"control": {"jerk_limit": 11.0}}),
    SeededCase("clean.fewer_phantoms", "clean", "control", "improvement: shorter-lived clutter",
               {"perception": {"fp_max_frames": 2}}),
    SeededCase("clean.better_peds", "clean", "control", "improvement: pedestrian miss rate 4% -> 3.5%",
               {"perception": {"ped_miss_rate": 0.035}}),
]


def all_cases() -> list[SeededCase]:
    return CASES + CONTROLS


def get(case_id: str) -> SeededCase:
    for c in all_cases():
        if c.id == case_id:
            return c
    raise KeyError(case_id)
