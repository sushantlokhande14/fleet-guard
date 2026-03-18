-- route_deviation: the candidate ends up further from the lane centre than the
-- baseline did on the same road (or leaves the lane where the baseline stayed in).
WITH off AS MATERIALIZED (
    SELECT scenario_id, min(t) AS first_t, count(*) AS n, max(value) AS worst_m
    FROM new_candidate_events
    WHERE campaign_id = %(campaign)s AND kind = 'off_route'
    GROUP BY scenario_id
)
SELECT
    pd.scenario_id,
    'route_deviation' AS category,
    least(1.0, greatest(pd.cand_cte_max - pd.base_cte_max, pd.lat_max_abs_diff)) AS score,
    coalesce(o.first_t, pd.first_divergence_t) AS first_t,
    jsonb_build_object(
        'cte_max_m', jsonb_build_array(round(pd.base_cte_max::numeric, 2), round(pd.cand_cte_max::numeric, 2)),
        'lat_max_abs_diff_m', round(pd.lat_max_abs_diff::numeric, 2),
        'first_divergence_s', round(pd.first_divergence_s::numeric, 1),
        'new_off_route_events', coalesce(o.n, 0),
        'lane_departure', pd.cand_reason = 'lane_departure'
    ) AS evidence
FROM pair_detail pd
LEFT JOIN off o ON o.scenario_id = pd.scenario_id
WHERE pd.campaign_id = %(campaign)s
  AND ((pd.cand_cte_max >= %(route_cte_floor_m)s
        AND pd.cand_cte_max - pd.base_cte_max >= %(route_cte_delta_m)s)
       OR pd.lat_max_abs_diff >= %(route_lat_diff_m)s
       OR o.n > 0
       OR (pd.cand_reason = 'lane_departure' AND pd.base_reason <> 'lane_departure'))
