-- Store short-lived map viewers so the GPS worker only pays for matching while a map is open.
BEGIN;
CREATE TABLE IF NOT EXISTS gps.map_matching_watchers (
    session_id text PRIMARY KEY,
    user_id bigint NOT NULL,
    expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS gps_map_matching_watchers_expires_idx
    ON gps.map_matching_watchers (expires_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON gps.map_matching_watchers TO sana_user;
COMMIT;
