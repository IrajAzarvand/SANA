-- Neshan road-matched coordinates are stored separately from raw GPS history.
-- Run as a PostgreSQL administrator against sana_db after 0001_gps_schema.sql.
BEGIN;
SET ROLE sana_user;

CREATE TABLE IF NOT EXISTS gps.map_matched_position (
    history_id BIGINT PRIMARY KEY
        REFERENCES gps.location_history(id) ON DELETE CASCADE,
    device_id BIGINT NOT NULL
        REFERENCES public.fleet_device(id) ON DELETE CASCADE,
    device_time TIMESTAMPTZ NOT NULL,
    original_latitude NUMERIC(10,7) NOT NULL,
    original_longitude NUMERIC(10,7) NOT NULL,
    matched_latitude NUMERIC(10,7) NOT NULL,
    matched_longitude NUMERIC(10,7) NOT NULL,
    matched_geom geometry(Point, 4326) NOT NULL,
    provider VARCHAR(32) NOT NULL DEFAULT 'neshan',
    matched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_map_match_latitude CHECK (matched_latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_map_match_longitude CHECK (matched_longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS ix_map_matched_device_time
    ON gps.map_matched_position (device_id, device_time DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON gps.map_matched_position TO sana_user;

COMMIT;
