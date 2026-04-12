-- Generated diagnostic reports. Several per failure are kept (template, then LLM,
-- regenerated after a rerun...); the API serves the newest.
CREATE TABLE reports (
    id          bigserial PRIMARY KEY,
    failure_id  bigint NOT NULL REFERENCES failures(id) ON DELETE CASCADE,
    generator   text NOT NULL CHECK (generator IN ('template', 'llm')),
    model       text,
    markdown    text NOT NULL,
    narrative   jsonb,
    meta        jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX reports_failure_idx ON reports (failure_id, created_at DESC);
