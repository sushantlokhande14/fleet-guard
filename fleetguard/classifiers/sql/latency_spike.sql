-- latency_spike: the candidate planner misses more deadlines, runs measurably
-- closer to its budget, or trips the watchdog where the baseline did not.
WITH spikes AS (
    SELECT scenario_id, min(t) AS first_t, count(*) AS n, max(value) AS worst_ms
    FROM new_candidate_events
    WHERE campaign_id = %(campaign)s AND kind = 'latency_spike'
    GROUP BY scenario_id
)
SELECT
    pd.scenario_id,
    'latency_spike' AS category,
    least(1.0, 0.3
        + 0.1 * greatest(0, pd.cand_misses - pd.base_misses)
        + greatest(0, pd.cand_p99_ms - pd.base_p99_ms) / 100.0
        + CASE WHEN pd.cand_reason = 'planner_watchdog' THEN 0.3 ELSE 0 END) AS score,
    sp.first_t,
    jsonb_build_object(
        'deadline_misses', jsonb_build_array(pd.base_misses, pd.cand_misses),
        'planner_p99_ms', jsonb_build_array(round(pd.base_p99_ms::numeric, 1), round(pd.cand_p99_ms::numeric, 1)),
        'new_spike_events', coalesce(sp.n, 0),
        'worst_cycle_ms', round(sp.worst_ms::numeric, 1),
        'watchdog', pd.cand_reason = 'planner_watchdog'
    ) AS evidence
FROM pair_detail pd
LEFT JOIN spikes sp ON sp.scenario_id = pd.scenario_id
WHERE pd.campaign_id = %(campaign)s
  AND (pd.cand_misses - pd.base_misses >= %(latency_min_new_misses)s
       OR (pd.cand_p99_ms >= %(latency_p99_floor_ms)s
           AND pd.cand_p99_ms - pd.base_p99_ms >= %(latency_p99_delta_ms)s)
       OR (pd.cand_reason = 'planner_watchdog' AND pd.base_reason <> 'planner_watchdog'))
