-- V11: notification preferences for emitted budget/API events.

BEGIN TRANSACTION;

INSERT INTO tf_notification_prefs (pref_key, enabled, channel, updated_at) VALUES
  ('budget_threshold', TRUE, 'in_app', now()),
  ('api_error',        TRUE, 'in_app', now())
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version, applied_at, description)
VALUES (11, now(), 'Notification preferences for budget and API error events');

COMMIT;
