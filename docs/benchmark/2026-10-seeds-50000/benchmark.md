Benchmark run `51b8d5fc`: 60 campaigns, 700 scenarios each (seeds from 50000, classifiers 2026.10), 84,000 simulated drives.

| | result |
|---|---|
| seeded regressions reproduced | **38 / 50 (76%)** |
| injected category flagged | 38 / 50 |
| injected category ranked first | 36 / 50 |
| strongest failure replayed identically | 42 / 50 |
| clean controls flagged (false positives) | 1 / 10 |

| case | level | flagged | top category | failures | reproduced |
|---|---|---|---|---|---|
| perception_error.far_pedestrians.moderate | moderate | perception_error, control_instability | perception_error | 30 / 53 | yes |
| perception_error.far_pedestrians.severe | severe | perception_error, disengagement | perception_error | 59 / 98 | yes |
| perception_error.weather_range.moderate | moderate | perception_error | perception_error | 45 / 48 | yes |
| perception_error.weather_range.severe | severe | perception_error | perception_error | 81 / 87 | yes |
| perception_error.phantoms.moderate | moderate | perception_error | perception_error | 540 / 541 | yes |
| perception_error.phantoms.severe | severe | perception_error, control_instability | perception_error | 685 / 689 | yes |
| perception_error.range_calibration.moderate | moderate | control_instability | control_instability | 0 / 4 | no |
| perception_error.range_calibration.severe | severe | - | - | 0 / 2 | no |
| perception_error.slow_confirmation.moderate | moderate | - | - | 2 / 6 | no |
| perception_error.slow_confirmation.severe | severe | perception_error | perception_error | 22 / 26 | yes |
| latency_spike.spike_rate.moderate | moderate | latency_spike | latency_spike | 553 / 553 | yes |
| latency_spike.spike_rate.severe | severe | latency_spike | latency_spike | 690 / 690 | yes |
| latency_spike.spike_size.moderate | moderate | latency_spike | latency_spike | 25 / 25 | yes |
| latency_spike.spike_size.severe | severe | latency_spike | latency_spike | 34 / 34 | yes |
| latency_spike.per_object.moderate | moderate | latency_spike | latency_spike | 29 / 29 | yes |
| latency_spike.per_object.severe | severe | latency_spike | latency_spike | 97 / 98 | yes |
| latency_spike.mean_creep.moderate | moderate | latency_spike, control_instability | latency_spike | 382 / 394 | yes |
| latency_spike.mean_creep.severe | severe | latency_spike | latency_spike | 699 / 699 | yes |
| latency_spike.jitter.moderate | moderate | latency_spike, control_instability | latency_spike | 273 / 282 | yes |
| latency_spike.jitter.severe | severe | latency_spike, control_instability | latency_spike | 674 / 681 | yes |
| route_deviation.curve_offset.moderate | moderate | route_deviation, control_instability | route_deviation | 200 / 258 | yes |
| route_deviation.curve_offset.severe | severe | route_deviation, control_instability | route_deviation | 244 / 262 | yes |
| route_deviation.lateral_bias.moderate | moderate | control_instability, route_deviation, perception_error, disengagement | control_instability | 46 / 103 | yes |
| route_deviation.lateral_bias.severe | severe | route_deviation | route_deviation | 700 / 700 | yes |
| route_deviation.corner_cutting.moderate | moderate | route_deviation | route_deviation | 11 / 11 | yes |
| route_deviation.corner_cutting.severe | severe | route_deviation | route_deviation | 269 / 270 | yes |
| route_deviation.gentle_curve_offset.moderate | moderate | control_instability | control_instability | 0 / 250 | no |
| route_deviation.gentle_curve_offset.severe | severe | route_deviation | route_deviation | 397 / 397 | yes |
| route_deviation.stale_map.severe | severe | route_deviation | route_deviation | 100 / 100 | yes |
| route_deviation.lateral_bias.subtle | moderate | control_instability | control_instability | 0 / 31 | no |
| control_instability.steer_gain.moderate | moderate | route_deviation | route_deviation | 0 / 10 | no |
| control_instability.steer_gain.severe | severe | route_deviation | route_deviation | 0 / 100 | no |
| control_instability.actuator_delay.moderate | moderate | control_instability | control_instability | 66 / 66 | yes |
| control_instability.actuator_delay.severe | severe | control_instability | control_instability | 212 / 214 | yes |
| control_instability.short_lookahead.moderate | moderate | - | - | 2 / 2 | no |
| control_instability.short_lookahead.severe | severe | control_instability | control_instability | 41 / 41 | yes |
| control_instability.speed_gain.moderate | moderate | control_instability | control_instability | 42 / 42 | yes |
| control_instability.speed_gain.severe | severe | control_instability | control_instability | 155 / 155 | yes |
| control_instability.integral.moderate | moderate | - | - | 0 / 2 | no |
| control_instability.integral.severe | severe | - | - | 1 / 4 | no |
| disengagement.headway.moderate | moderate | control_instability | control_instability | 0 / 39 | no |
| disengagement.headway.severe | severe | control_instability, disengagement | control_instability | 60 / 263 | yes |
| disengagement.ped_yield.moderate | moderate | disengagement, control_instability, perception_error | disengagement | 14 / 31 | yes |
| disengagement.ped_yield.severe | severe | disengagement, control_instability, perception_error | disengagement | 47 / 72 | yes |
| disengagement.cut_in.moderate | moderate | disengagement | disengagement | 5 / 5 | yes |
| disengagement.cut_in.severe | severe | disengagement | disengagement | 14 / 17 | yes |
| disengagement.brake_cap.moderate | moderate | disengagement | disengagement | 4 / 8 | yes |
| disengagement.brake_cap.severe | severe | disengagement, control_instability, perception_error | disengagement | 20 / 31 | yes |
| disengagement.watchdog.moderate | moderate | - | - | 1 / 1 | no |
| disengagement.watchdog.severe | severe | disengagement, control_instability, perception_error | disengagement | 422 / 465 | yes |
| clean.identical | control | - | - | 0 | pass |
| clean.max_accel | control | - | - | 0 | pass |
| clean.comfort_decel | control | - | - | 0 | pass |
| clean.perception_latency | control | - | - | 0 | pass |
| clean.position_noise | control | control_instability | control_instability | 4 | FALSE POSITIVE |
| clean.planner_mean | control | - | - | 0 | pass |
| clean.lookahead_min | control | - | - | 0 | pass |
| clean.jerk_limit | control | - | - | 2 | pass |
| clean.fewer_phantoms | control | - | - | 1 | pass |
| clean.better_peds | control | - | - | 0 | pass |
