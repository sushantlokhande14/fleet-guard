-- latency_spike: the candidate planner misses more deadlines, runs closer to its
-- budget, or trips the watchdog because it got slower.
--
-- Counts are compared only up to the moment both drives were still running: a
-- candidate that ends early has fewer cycles, one that runs longer has more, and
-- shared random draws mean the extra cycles carry their own spikes. Comparing
-- whole-drive totals blamed latency for regressions that only changed drive
-- length (2026.03 benchmark, control_instability.integral.severe).
--
-- A p99 shift counts when both drives completed or new near-budget cycles back it
-- up: over a few hundred cycles p99 is about the third-worst cycle.
WITH win AS MATERIALIZED (
    SELECT p.scenario_id, p.baseline_drive, p.candidate_drive, least(b.duration_s, c.duration_s) AS t_end
      FROM pairs p
      JOIN drives b ON b.id = p.baseline_drive
      JOIN drives c ON c.id = p.candidate_drive
     WHERE p.campaign_id = %(campaign)s
),
misses AS MATERIALIZED (
    SELECT w.scenario_id,
           count(*) FILTER (WHERE e.drive_id = w.baseline_drive) AS base_n,
           count(*) FILTER (WHERE e.drive_id = w.candidate_drive) AS cand_n
      FROM win w
      JOIN drive_events e ON e.drive_id IN (w.baseline_drive, w.candidate_drive)
     WHERE e.kind = 'latency_spike' AND e.detail = 'deadline_miss' AND e.t <= w.t_end
     GROUP BY w.scenario_id
),
spikes AS MATERIALIZED (
    SELECT n.scenario_id, min(n.t) AS first_t, count(*) AS n, max(n.value) AS worst_ms
      FROM new_candidate_events n
      JOIN win w ON w.scenario_id = n.scenario_id
     WHERE n.campaign_id = %(campaign)s AND n.kind = 'latency_spike' AND n.t <= w.t_end
     GROUP BY n.scenario_id
)
SELECT
    pd.scenario_id,
    'latency_spike' AS category,
    least(1.0, 0.3
        + 0.1 * greatest(0, coalesce(m.cand_n, 0) - coalesce(m.base_n, 0))
        + greatest(0, pd.cand_p99_ms - pd.base_p99_ms) / 100.0
        + CASE WHEN pd.cand_reason = 'planner_watchdog' THEN 0.3 ELSE 0 END) AS score,
    sp.first_t,
    jsonb_build_object(
        'deadline_misses', jsonb_build_array(coalesce(m.base_n, 0), coalesce(m.cand_n, 0)),
        'compared_until_s', round(w.t_end::numeric, 1),
        'planner_p99_ms', jsonb_build_array(round(pd.base_p99_ms::numeric, 1), round(pd.cand_p99_ms::numeric, 1)),
        'new_spike_events', coalesce(sp.n, 0),
        'worst_cycle_ms', round(sp.worst_ms::numeric, 1),
        'watchdog', pd.cand_reason = 'planner_watchdog'
    ) AS evidence
FROM pair_detail pd
JOIN win w ON w.scenario_id = pd.scenario_id
LEFT JOIN misses m ON m.scenario_id = pd.scenario_id
LEFT JOIN spikes sp ON sp.scenario_id = pd.scenario_id
WHERE pd.campaign_id = %(campaign)s
  AND (coalesce(m.cand_n, 0) - coalesce(m.base_n, 0) >= %(latency_min_new_misses)s
       OR (pd.cand_p99_ms >= %(latency_p99_floor_ms)s
           AND pd.cand_p99_ms - pd.base_p99_ms >= %(latency_p99_delta_ms)s
           AND (coalesce(sp.n, 0) >= %(latency_min_new_events)s
                OR (pd.base_outcome = 'completed' AND pd.cand_outcome = 'completed')))
       OR (pd.cand_reason = 'planner_watchdog' AND pd.base_reason <> 'planner_watchdog'))
