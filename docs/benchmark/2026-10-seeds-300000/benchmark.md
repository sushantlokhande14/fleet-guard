Benchmark run `545f600f`: 60 campaigns, 700 scenarios each (seeds from 300000, classifiers 2026.10), 84,000 simulated drives.

| | result |
|---|---|
| seeded regressions reproduced | **38 / 50 (76%)** |
| injected category flagged | 38 / 50 |
| injected category ranked first | 36 / 50 |
| strongest failure replayed identically | 44 / 50 |
| clean controls flagged (false positives) | 1 / 10 |

| case | level | flagged | top category | failures | reproduced |
|---|---|---|---|---|---|
| perception_error.far_pedestrians.moderate | moderate | perception_error, control_instability | perception_error | 43 / 63 | yes |
| perception_error.far_pedestrians.severe | severe | perception_error, disengagement | perception_error | 63 / 97 | yes |
| perception_error.weather_range.moderate | moderate | perception_error, control_instability | perception_error | 49 / 53 | yes |
| perception_error.weather_range.severe | severe | perception_error, control_instability | perception_error | 82 / 89 | yes |
| perception_error.phantoms.moderate | moderate | perception_error | perception_error | 551 / 554 | yes |
| perception_error.phantoms.severe | severe | perception_error, control_instability | perception_error | 682 / 686 | yes |
| perception_error.range_calibration.moderate | moderate | control_instability | control_instability | 2 / 9 | no |
| perception_error.range_calibration.severe | severe | disengagement | disengagement | 3 / 11 | no |
| perception_error.slow_confirmation.moderate | moderate | - | - | 2 / 4 | no |
| perception_error.slow_confirmation.severe | severe | perception_error | perception_error | 23 / 26 | yes |
| latency_spike.spike_rate.moderate | moderate | latency_spike | latency_spike | 533 / 533 | yes |
| latency_spike.spike_rate.severe | severe | latency_spike | latency_spike | 698 / 698 | yes |
| latency_spike.spike_size.moderate | moderate | latency_spike | latency_spike | 7 / 7 | yes |
| latency_spike.spike_size.severe | severe | latency_spike | latency_spike | 8 / 8 | yes |
| latency_spike.per_object.moderate | moderate | latency_spike | latency_spike | 26 / 27 | yes |
| latency_spike.per_object.severe | severe | latency_spike | latency_spike | 96 / 96 | yes |
| latency_spike.mean_creep.moderate | moderate | latency_spike, control_instability | latency_spike | 262 / 274 | yes |
| latency_spike.mean_creep.severe | severe | latency_spike | latency_spike | 698 / 699 | yes |
| latency_spike.jitter.moderate | moderate | latency_spike, control_instability | latency_spike | 164 / 170 | yes |
| latency_spike.jitter.severe | severe | latency_spike | latency_spike | 693 / 696 | yes |
| route_deviation.curve_offset.moderate | moderate | route_deviation, control_instability | route_deviation | 200 / 265 | yes |
| route_deviation.curve_offset.severe | severe | route_deviation, control_instability | route_deviation | 247 / 267 | yes |
| route_deviation.lateral_bias.moderate | moderate | control_instability, route_deviation, disengagement, perception_error | control_instability | 36 / 89 | yes |
| route_deviation.lateral_bias.severe | severe | route_deviation | route_deviation | 700 / 700 | yes |
| route_deviation.corner_cutting.moderate | moderate | route_deviation | route_deviation | 8 / 8 | yes |
| route_deviation.corner_cutting.severe | severe | route_deviation | route_deviation | 274 / 275 | yes |
| route_deviation.gentle_curve_offset.moderate | moderate | control_instability | control_instability | 0 / 250 | no |
| route_deviation.gentle_curve_offset.severe | severe | route_deviation | route_deviation | 393 / 393 | yes |
| route_deviation.stale_map.severe | severe | route_deviation | route_deviation | 100 / 100 | yes |
| route_deviation.lateral_bias.subtle | moderate | control_instability | control_instability | 0 / 38 | no |
| control_instability.steer_gain.moderate | moderate | route_deviation | route_deviation | 0 / 12 | no |
| control_instability.steer_gain.severe | severe | route_deviation | route_deviation | 0 / 99 | no |
| control_instability.actuator_delay.moderate | moderate | control_instability | control_instability | 67 / 68 | yes |
| control_instability.actuator_delay.severe | severe | control_instability | control_instability | 209 / 211 | yes |
| control_instability.short_lookahead.moderate | moderate | - | - | 1 / 1 | no |
| control_instability.short_lookahead.severe | severe | control_instability | control_instability | 42 / 42 | yes |
| control_instability.speed_gain.moderate | moderate | control_instability | control_instability | 44 / 46 | yes |
| control_instability.speed_gain.severe | severe | control_instability | control_instability | 154 / 156 | yes |
| control_instability.integral.moderate | moderate | - | - | 0 / 1 | no |
| control_instability.integral.severe | severe | - | - | 1 / 2 | no |
| disengagement.headway.moderate | moderate | control_instability | control_instability | 0 / 62 | no |
| disengagement.headway.severe | severe | control_instability, disengagement | control_instability | 56 / 270 | yes |
| disengagement.ped_yield.moderate | moderate | disengagement, control_instability | disengagement | 13 / 28 | yes |
| disengagement.ped_yield.severe | severe | disengagement, control_instability, perception_error | disengagement | 48 / 73 | yes |
| disengagement.cut_in.moderate | moderate | disengagement | disengagement | 12 / 12 | yes |
| disengagement.cut_in.severe | severe | disengagement | disengagement | 21 / 24 | yes |
| disengagement.brake_cap.moderate | moderate | disengagement | disengagement | 4 / 8 | yes |
| disengagement.brake_cap.severe | severe | disengagement | disengagement | 18 / 24 | yes |
| disengagement.watchdog.moderate | moderate | - | - | 1 / 1 | no |
| disengagement.watchdog.severe | severe | disengagement, control_instability, perception_error | disengagement | 424 / 467 | yes |
| clean.identical | control | - | - | 0 | pass |
| clean.max_accel | control | - | - | 4 | pass |
| clean.comfort_decel | control | - | - | 0 | pass |
| clean.perception_latency | control | - | - | 0 | pass |
| clean.position_noise | control | control_instability | control_instability | 5 | FALSE POSITIVE |
| clean.planner_mean | control | - | - | 0 | pass |
| clean.lookahead_min | control | - | - | 0 | pass |
| clean.jerk_limit | control | - | - | 1 | pass |
| clean.fewer_phantoms | control | - | - | 0 | pass |
| clean.better_peds | control | - | - | 1 | pass |
