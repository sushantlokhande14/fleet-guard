-- Classified regressions: at most one failure per (campaign, scenario), with a
-- primary category, every other signal that fired, and a cluster signature.

CREATE TABLE failures (
    id                 bigserial PRIMARY KEY,
    campaign_id        bigint NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    scenario_id        text NOT NULL REFERENCES scenarios(id),
    category           text NOT NULL CHECK (category IN (
                           'disengagement', 'latency_spike', 'route_deviation',
                           'perception_error', 'control_instability')),
    secondary          text[] NOT NULL DEFAULT '{}',
    severity           smallint NOT NULL CHECK (severity BETWEEN 1 AND 3),
    score              real NOT NULL,
    first_t            real,
    signature          text NOT NULL,
    evidence           jsonb NOT NULL,
    signals            jsonb NOT NULL,
    classifier_version text NOT NULL,
    repro_verified     boolean,
    repro_checked_at   timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (campaign_id, scenario_id)
);
CREATE INDEX failures_campaign_idx ON failures (campaign_id, category);
CREATE INDEX failures_signature_idx ON failures (campaign_id, signature);

ALTER TABLE campaigns ADD COLUMN verdict jsonb;

