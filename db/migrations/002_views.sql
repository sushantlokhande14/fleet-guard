-- Read-side views over campaign telemetry. Grafana, the API and the classifiers
-- all query these instead of re-deriving the same aggregates.

-- One row per (campaign, role): fleet-level KPIs for each build.
CREATE VIEW campaign_role_metrics AS
SELECT
    d.campaign_id,
    d.role,
    min(d.build)                                                          AS build,
    count(*)                                                              AS drives,
    count(*) FILTER (WHERE d.outcome = 'completed')                       AS completed,
    count(*) FILTER (WHERE d.outcome = 'disengaged')                      AS disengaged,
    count(*) FILTER (WHERE d.outcome = 'collision')                       AS collisions,
    count(*) FILTER (WHERE d.outcome = 'timeout')                         AS timeouts,
    sum(d.distance_m) / 1000.0                                            AS km,
    1000.0 * count(*) FILTER (WHERE d.outcome IN ('disengaged', 'collision'))
        / nullif(sum(d.distance_m) / 1000.0, 0)                           AS disengagements_per_1000km,
    100.0 * sum(d.hard_brakes) / nullif(sum(d.distance_m) / 1000.0, 0)    AS hard_brakes_per_100km,
    sum(d.det_tp)::real / nullif(sum(d.det_tp) + sum(d.det_fn), 0)        AS recall,
    sum(d.det_tp)::real / nullif(sum(d.det_tp) + sum(d.det_fp), 0)        AS precision,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY d.planner_p99_ms)         AS planner_p99_median_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY d.planner_p99_ms)        AS planner_p99_p99_ms,
    max(d.planner_max_ms)                                                 AS planner_max_ms,
    sum(d.deadline_misses)                                                AS deadline_misses,
    avg(d.cte_p95)                                                        AS cte_p95_mean,
    max(d.cte_max)                                                        AS cte_max,
    avg(d.steer_reversal_rate)                                            AS steer_reversal_rate,
    avg(d.accel_reversal_rate)                                            AS accel_reversal_rate,
    avg(d.jerk_rms)                                                       AS jerk_rms
FROM drives d
GROUP BY d.campaign_id, d.role;

-- Same KPIs split by scenario family.
CREATE VIEW campaign_family_metrics AS
SELECT
    d.campaign_id,
    s.family,
    d.role,
    count(*)                                                        AS drives,
    count(*) FILTER (WHERE d.outcome <> 'completed')                AS failed,
    count(*) FILTER (WHERE d.outcome = 'collision')                 AS collisions,
    sum(d.det_tp)::real / nullif(sum(d.det_tp) + sum(d.det_fn), 0)  AS recall,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY d.planner_p99_ms)  AS planner_p99_p99_ms,
    avg(d.cte_p95)                                                  AS cte_p95_mean,
    avg(d.steer_reversal_rate)                                      AS steer_reversal_rate
FROM drives d
JOIN scenarios s ON s.id = d.scenario_id
GROUP BY d.campaign_id, s.family, d.role;

-- Each scenario pair with both drives side by side. The classifiers start here.
CREATE VIEW pair_detail AS
SELECT
    p.*,
    s.family,
    s.weather,
    b.outcome  AS base_outcome,
    b.reason   AS base_reason,
    c.outcome  AS cand_outcome,
    c.reason   AS cand_reason,
    b.cte_max  AS base_cte_max,
    c.cte_max  AS cand_cte_max,
    b.planner_p99_ms AS base_p99_ms,
    c.planner_p99_ms AS cand_p99_ms,
    b.deadline_misses AS base_misses,
    c.deadline_misses AS cand_misses,
    b.recall   AS base_recall,
    c.recall   AS cand_recall,
    b.steer_reversal_rate AS base_steer_rev,
    c.steer_reversal_rate AS cand_steer_rev,
    b.accel_reversal_rate AS base_accel_rev,
    c.accel_reversal_rate AS cand_accel_rev,
    b.jerk_rms AS base_jerk,
    c.jerk_rms AS cand_jerk
FROM pairs p
JOIN scenarios s ON s.id = p.scenario_id
JOIN drives b ON b.id = p.baseline_drive
JOIN drives c ON c.id = p.candidate_drive;

-- Events of the candidate drive that the baseline drive did not have (same kind,
-- matched within 0.5 s). Shared luck between builds means most baseline events
-- reappear at the same time in the candidate; what is left is new behaviour.
CREATE VIEW new_candidate_events AS
SELECT p.campaign_id, p.scenario_id, ce.*
FROM pairs p
JOIN drive_events ce ON ce.drive_id = p.candidate_drive
WHERE NOT EXISTS (
    SELECT 1 FROM drive_events be
    WHERE be.drive_id = p.baseline_drive
      AND be.kind = ce.kind
      AND abs(be.t - ce.t) <= 0.5
);
