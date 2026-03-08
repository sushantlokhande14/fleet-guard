-- control_instability: steering or speed control rings where the baseline was
-- calm: clearly more direction reversals per second, repeated new oscillation
-- episodes (a single one must come with more reversals: car following on the
-- highway sits close to the detector threshold), or a clearly higher jerk.
WITH osc AS (
    SELECT scenario_id, min(t) AS first_t, count(*) AS n,
           array_agg(DISTINCT kind) AS kinds
    FROM new_candidate_events
    WHERE campaign_id = %(campaign)s AND kind IN ('steer_oscillation', 'accel_oscillation')
    GROUP BY scenario_id
)
SELECT
    pd.scenario_id,
    'control_instability' AS category,
    least(1.0, 2 * greatest(0, pd.d_steer_reversal_rate) + 2 * greatest(0, pd.d_accel_reversal_rate)
        + 0.3 * coalesce(o.n, 0)) AS score,
    o.first_t,
    jsonb_build_object(
        'steer_reversals_per_s', jsonb_build_array(round(pd.base_steer_rev::numeric, 3),
                                                  round(pd.cand_steer_rev::numeric, 3)),
        'accel_reversals_per_s', jsonb_build_array(round(pd.base_accel_rev::numeric, 3),
                                                  round(pd.cand_accel_rev::numeric, 3)),
        'jerk_rms', jsonb_build_array(round(pd.base_jerk::numeric, 2), round(pd.cand_jerk::numeric, 2)),
        'oscillation_events', coalesce(o.n, 0),
        'axes', coalesce(to_jsonb(o.kinds), '[]'::jsonb)
    ) AS evidence
FROM pair_detail pd
LEFT JOIN osc o ON o.scenario_id = pd.scenario_id
WHERE pd.campaign_id = %(campaign)s
  AND (pd.d_steer_reversal_rate >= %(ctrl_steer_rev_delta)s
       OR pd.d_accel_reversal_rate >= %(ctrl_accel_rev_delta)s
       OR o.n >= 2
       OR (o.n = 1 AND greatest(pd.d_steer_reversal_rate, pd.d_accel_reversal_rate) >= %(ctrl_rev_with_event)s)
       OR (pd.d_jerk_rms >= %(ctrl_jerk_delta)s AND pd.cand_jerk >= 1.5 * pd.base_jerk))
