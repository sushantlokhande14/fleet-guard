-- Wall time per phase (simulate, ingest, classify) so large campaigns show where the time goes.
ALTER TABLE campaigns ADD COLUMN timings jsonb;
