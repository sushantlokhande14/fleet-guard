-- Alerts received from Alertmanager's webhook, one row per alert fingerprint.
CREATE TABLE alerts (
    fingerprint  text PRIMARY KEY,
    alertname    text NOT NULL,
    status       text NOT NULL CHECK (status IN ('firing', 'resolved')),
    severity     text,
    campaign_id  bigint REFERENCES campaigns(id) ON DELETE SET NULL,
    labels       jsonb NOT NULL,
    annotations  jsonb NOT NULL,
    starts_at    timestamptz NOT NULL,
    ends_at      timestamptz,
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX alerts_status_idx ON alerts (status, starts_at DESC);
