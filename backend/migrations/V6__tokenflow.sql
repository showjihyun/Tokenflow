-- V6: Token Flow-specific tables.
-- Adds per-message records (from JSONL transcripts), tailer offsets, and a single-row config.

BEGIN TRANSACTION;

-- Per-message records parsed from Claude Code JSONL transcripts.
CREATE TABLE IF NOT EXISTS tf_messages (
    message_id                VARCHAR PRIMARY KEY,
    session_id                VARCHAR NOT NULL,
    ts                        TIMESTAMP NOT NULL,
    role                      VARCHAR NOT NULL,
    model                     VARCHAR,
    input_tokens              INTEGER DEFAULT 0,
    output_tokens             INTEGER DEFAULT 0,
    cache_creation_tokens     INTEGER DEFAULT 0,
    cache_read_tokens         INTEGER DEFAULT 0,
    cost_usd                  DOUBLE DEFAULT 0,
    content_preview           VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_tf_msg_session_ts ON tf_messages(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_tf_msg_ts ON tf_messages(ts DESC);
CREATE INDEX IF NOT EXISTS idx_tf_msg_model ON tf_messages(model);

-- Persistent file read offsets so we don't reprocess on restart.
CREATE TABLE IF NOT EXISTS tf_transcript_offsets (
    transcript_path           VARCHAR PRIMARY KEY,
    session_id                VARCHAR NOT NULL,
    bytes_read                BIGINT NOT NULL DEFAULT 0,
    last_read_at              TIMESTAMP NOT NULL
);

-- Same idea for the hook ndjson stream.
CREATE TABLE IF NOT EXISTS tf_hook_offset (
    id                        INTEGER PRIMARY KEY,
    bytes_read                BIGINT NOT NULL DEFAULT 0,
    last_read_at              TIMESTAMP
);
INSERT INTO tf_hook_offset (id, bytes_read) VALUES (1, 0) ON CONFLICT DO NOTHING;

-- Single-row config table for budget + tweaks persistence.
CREATE TABLE IF NOT EXISTS tf_config (
    id                        INTEGER PRIMARY KEY,
    monthly_budget_usd        DOUBLE DEFAULT 150.0,
    alert_thresholds_pct      VARCHAR DEFAULT '[50,75,90]',
    hard_block                BOOLEAN DEFAULT FALSE,
    better_prompt_mode        VARCHAR DEFAULT 'static',
    theme                     VARCHAR DEFAULT 'dark',
    density                   VARCHAR DEFAULT 'normal',
    chart_style               VARCHAR DEFAULT 'bold',
    sidebar_pos               VARCHAR DEFAULT 'left',
    alert_level               VARCHAR DEFAULT 'balanced',
    lang                      VARCHAR DEFAULT 'ko',
    onboarded_at              TIMESTAMP,
    created_at                TIMESTAMP NOT NULL,
    updated_at                TIMESTAMP
);

INSERT INTO tf_config (id, created_at) VALUES (1, now()) ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (6, now(), 'Token Flow messages, offsets, config');

COMMIT;
