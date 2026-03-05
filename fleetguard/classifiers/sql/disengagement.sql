-- disengagement: the baseline completed the scenario, the candidate did not
-- (safety-driver takeover, planner watchdog, collision or timeout).
SELECT
    pd.scenario_id,
    'disengagement' AS category,
    CASE pd.cand_outcome WHEN 'collision' THEN 1.0 WHEN 'disengaged' THEN 0.9 ELSE 0.6 END AS score,
    coalesce(ev.t, c.duration_s) AS first_t,
    jsonb_build_object(
        'outcome', pd.cand_outcome,
        'reason', pd.cand_reason,
        'detail', ev.detail,
        'value', ev.value,
        'at_s', round(coalesce(ev.t, c.duration_s)::numeric, 2),
        'route_completion', round(c.route_completion::numeric, 3),
        'baseline_outcome', pd.base_outcome
    ) AS evidence
FROM pair_detail pd
JOIN drives c ON c.id = pd.candidate_drive
LEFT JOIN LATERAL (
    SELECT e.t, e.detail, e.value
    FROM drive_events e
    WHERE e.drive_id = pd.candidate_drive AND e.kind IN ('disengagement', 'collision')
    ORDER BY e.t
    LIMIT 1
) ev ON true
WHERE pd.campaign_id = %(campaign)s
  AND pd.base_outcome = 'completed'
  AND pd.cand_outcome <> 'completed'
