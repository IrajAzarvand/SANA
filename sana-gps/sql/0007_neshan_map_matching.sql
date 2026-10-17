-- Retired before this migration was merged to main.
-- Earlier deployments may already have created gps.map_matched_position.
-- Migration 0008 moves any stored matches into gps.location_history/current_state
-- and removes the temporary table. New installations should not create it.
BEGIN;
SET ROLE sana_user;
COMMIT;
