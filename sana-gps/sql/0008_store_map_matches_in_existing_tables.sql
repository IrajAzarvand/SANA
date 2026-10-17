-- Move road-matched coordinates into the existing GPS tables.
-- Migration 0007 may already have created map_matched_position on an existing server.
-- Preserve any matches already written before removing that temporary table.
BEGIN;
SET ROLE sana_user;

ALTER TABLE gps.location_history
    ADD COLUMN IF NOT EXISTS matched_latitude NUMERIC(10,7),
    ADD COLUMN IF NOT EXISTS matched_longitude NUMERIC(10,7),
    ADD COLUMN IF NOT EXISTS matched_geom geometry(Point, 4326),
    ADD COLUMN IF NOT EXISTS match_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS matched_at TIMESTAMPTZ;

ALTER TABLE gps.current_state
    ADD COLUMN IF NOT EXISTS matched_latitude NUMERIC(10,7),
    ADD COLUMN IF NOT EXISTS matched_longitude NUMERIC(10,7),
    ADD COLUMN IF NOT EXISTS matched_geom geometry(Point, 4326),
    ADD COLUMN IF NOT EXISTS match_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS matched_at TIMESTAMPTZ;

-- Move existing per-history matches to the corresponding history row.
UPDATE gps.location_history AS h
SET matched_latitude = m.matched_latitude,
    matched_longitude = m.matched_longitude,
    matched_geom = m.matched_geom,
    match_provider = m.provider,
    matched_at = m.matched_at
FROM gps.map_matched_position AS m
WHERE m.history_id = h.id;

-- Only copy a match into current_state when it refers to the exact current
-- or last-valid raw fix. Never let an older matched point move a newer marker.
UPDATE gps.current_state AS s
SET matched_latitude = m.matched_latitude,
    matched_longitude = m.matched_longitude,
    matched_geom = m.matched_geom,
    match_provider = m.provider,
    matched_at = m.matched_at
FROM gps.map_matched_position AS m
WHERE m.device_id = s.device_id
  AND m.device_time = COALESCE(
      CASE WHEN s.gps_valid THEN s.device_time ELSE s.last_valid_device_time END,
      s.device_time
  )
  AND m.original_latitude = COALESCE(
      CASE WHEN s.gps_valid THEN s.latitude ELSE s.last_valid_latitude END,
      s.latitude
  )
  AND m.original_longitude = COALESCE(
      CASE WHEN s.gps_valid THEN s.longitude ELSE s.last_valid_longitude END,
      s.longitude
  );

DROP TABLE IF EXISTS gps.map_matched_position;

COMMIT;
