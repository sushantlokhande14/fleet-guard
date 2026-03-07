-- perception_error: the candidate's tracker finds fewer of the real objects in
-- front of it, or reports more phantoms, than the baseline's on the same drive.
WITH misses AS (
    SELECT scenario_id, min(t) AS first_t, count(*) AS n,
           jsonb_agg(jsonb_build_object('t', round(t::numeric, 1), 'object', detail,
                                        'range_m', round(value::numeric, 1)) ORDER BY t) AS items
    FROM new_candidate_events
    WHERE campaign_id = %(campaign)s AND kind = 'perception_miss'
    GROUP BY scenario_id
),
phantoms AS (
    SELECT scenario_id, min(t) AS first_t, count(*) AS n
    FROM new_candidate_events
    WHERE campaign_id = %(campaign)s AND kind = 'phantom_object'
    GROUP BY scenario_id
)
SELECT
    pd.scenario_id,
    'perception_error' AS category,
    least(1.0, 5 * greatest(0, -pd.d_recall, -pd.d_precision)
        + 0.3 * coalesce(m.n, 0) + 0.2 * coalesce(ph.n, 0)) AS score,
    least(m.first_t, ph.first_t) AS first_t,
    jsonb_build_object(
        'recall', jsonb_build_array(round(pd.base_recall::numeric, 3), round(pd.cand_recall::numeric, 3)),
        'precision_delta', round(pd.d_precision::numeric, 3),
        'new_misses', coalesce(m.items, '[]'::jsonb),
        'new_phantoms', coalesce(ph.n, 0)
    ) AS evidence
FROM pair_detail pd
LEFT JOIN misses m ON m.scenario_id = pd.scenario_id
LEFT JOIN phantoms ph ON ph.scenario_id = pd.scenario_id
WHERE pd.campaign_id = %(campaign)s
  AND (pd.d_recall <= -%(perc_recall_drop)s
       OR pd.d_precision <= -%(perc_precision_drop)s
       OR m.n > 0
       OR ph.n > 0)
