-- Run once as a PostgreSQL administrator after the GPS schema is installed.
-- Keep this function owned by sana_owner; do not grant runtime roles direct DELETE.
BEGIN;

CREATE OR REPLACE FUNCTION gps.purge_device_data(p_device_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, gps
AS $$
BEGIN
    -- Delete dependents first because several GPS tables intentionally use ON DELETE RESTRICT.
    DELETE FROM gps.trip WHERE device_id = p_device_id;
    DELETE FROM gps.event WHERE device_id = p_device_id;
    DELETE FROM gps.vehicle_geofence_state WHERE device_id = p_device_id;
    DELETE FROM gps.location_history WHERE device_id = p_device_id;
    DELETE FROM gps.current_state WHERE device_id = p_device_id;
    DELETE FROM gps.raw_packet WHERE device_id = p_device_id;
END;
$$;

ALTER FUNCTION gps.purge_device_data(BIGINT) OWNER TO sana_owner;
REVOKE ALL ON FUNCTION gps.purge_device_data(BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gps.purge_device_data(BIGINT) TO sana_backend;

COMMIT;
