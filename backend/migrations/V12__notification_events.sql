-- V12: persisted in-app notification events for the Topbar Bell.

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS tf_notifications (
    id          VARCHAR PRIMARY KEY,
    pref_key    VARCHAR NOT NULL,
    title       VARCHAR NOT NULL,
    body        VARCHAR NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    read_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tf_notifications_created
ON tf_notifications(created_at);

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (12, now(), 'Persisted in-app notification events');

COMMIT;
