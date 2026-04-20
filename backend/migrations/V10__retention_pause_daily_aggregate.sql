-- V10: paused transcript marker + daily aggregate rollup for retention.

BEGIN TRANSACTION;

ALTER TABLE tf_messages ADD COLUMN IF NOT EXISTS paused BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_tf_msg_paused_ts ON tf_messages(paused, ts);

CREATE TABLE IF NOT EXISTS daily_aggregate (
    day                       DATE NOT NULL,
    project_slug              VARCHAR NOT NULL,
    model_key                 VARCHAR NOT NULL,
    input_tokens              BIGINT DEFAULT 0,
    output_tokens             BIGINT DEFAULT 0,
    cache_creation_tokens     BIGINT DEFAULT 0,
    cache_read_tokens         BIGINT DEFAULT 0,
    cost_usd                  DOUBLE DEFAULT 0,
    messages                  BIGINT DEFAULT 0,
    updated_at                TIMESTAMP NOT NULL,
    PRIMARY KEY (day, project_slug, model_key)
);

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (10, now(), 'Paused transcript marker and daily aggregate rollup');

COMMIT;
