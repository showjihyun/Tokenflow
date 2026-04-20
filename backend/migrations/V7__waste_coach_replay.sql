-- V7: Phase E tables — waste patterns, coach threads/messages, better prompt cache,
-- routing rules, notification preferences.

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS tf_waste_patterns (
    id                        VARCHAR PRIMARY KEY,
    kind                      VARCHAR NOT NULL,
    severity                  VARCHAR NOT NULL,
    title                     VARCHAR NOT NULL,
    meta                      VARCHAR,
    body_html                 VARCHAR,
    save_tokens               INTEGER DEFAULT 0,
    save_usd                  DOUBLE DEFAULT 0,
    sessions                  INTEGER DEFAULT 1,
    session_id                VARCHAR,
    context                   JSON,
    detected_at               TIMESTAMP NOT NULL,
    dismissed_at              TIMESTAMP,
    applied_at                TIMESTAMP,
    applied_outcome           VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_waste_severity ON tf_waste_patterns(severity);
CREATE INDEX IF NOT EXISTS idx_waste_kind ON tf_waste_patterns(kind);
CREATE INDEX IF NOT EXISTS idx_waste_detected ON tf_waste_patterns(detected_at DESC);

CREATE TABLE IF NOT EXISTS tf_coach_threads (
    id                        VARCHAR PRIMARY KEY,
    title                     VARCHAR,
    started_at                TIMESTAMP NOT NULL,
    last_msg_at               TIMESTAMP,
    cost_usd_total            DOUBLE DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_coach_thread_updated ON tf_coach_threads(last_msg_at DESC);

CREATE TABLE IF NOT EXISTS tf_coach_messages (
    id                        VARCHAR PRIMARY KEY,
    thread_id                 VARCHAR NOT NULL,
    role                      VARCHAR NOT NULL,
    content                   VARCHAR NOT NULL,
    ts                        TIMESTAMP NOT NULL,
    context_snapshot_json     JSON,
    input_tokens              INTEGER DEFAULT 0,
    output_tokens             INTEGER DEFAULT 0,
    cost_usd                  DOUBLE DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_coach_msg_thread ON tf_coach_messages(thread_id, ts);

CREATE TABLE IF NOT EXISTS tf_better_prompt (
    cache_key                 VARCHAR PRIMARY KEY,
    session_id                VARCHAR NOT NULL,
    msg_index                 INTEGER NOT NULL,
    mode                      VARCHAR NOT NULL,
    suggested_text            VARCHAR NOT NULL,
    est_save_tokens           INTEGER DEFAULT 0,
    cached_at                 TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS tf_routing_rules (
    id                        VARCHAR PRIMARY KEY,
    condition_pattern         VARCHAR NOT NULL,
    target_model              VARCHAR NOT NULL,
    enabled                   BOOLEAN DEFAULT TRUE,
    priority                  INTEGER DEFAULT 100,
    created_at                TIMESTAMP NOT NULL,
    updated_at                TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tf_notification_prefs (
    pref_key                  VARCHAR PRIMARY KEY,
    enabled                   BOOLEAN DEFAULT TRUE,
    channel                   VARCHAR DEFAULT 'in_app',
    updated_at                TIMESTAMP
);

INSERT INTO tf_notification_prefs (pref_key, enabled, channel, updated_at) VALUES
  ('waste_high',         TRUE,  'in_app', now()),
  ('context_saturation', TRUE,  'in_app', now()),
  ('opus_overuse',       TRUE,  'in_app', now()),
  ('daily_report',       FALSE, 'in_app', now()),
  ('weekly_summary',     TRUE,  'in_app', now()),
  ('session_summary',    FALSE, 'in_app', now())
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (7, now(), 'Phase E: waste, coach, better_prompt, routing, notifications');

COMMIT;
