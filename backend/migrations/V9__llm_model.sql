-- V9: selected LLM model for coach/replay features.

BEGIN TRANSACTION;

ALTER TABLE tf_config ADD COLUMN IF NOT EXISTS llm_model VARCHAR DEFAULT 'claude-sonnet-4-6';

UPDATE tf_config
SET llm_model = COALESCE(llm_model, 'claude-sonnet-4-6')
WHERE id = 1;

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (9, now(), 'Selected LLM model for coach and replay');

COMMIT;
