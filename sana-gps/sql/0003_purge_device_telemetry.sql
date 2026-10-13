-- Run once as a PostgreSQL administrator after the GPS schema is installed.
-- Keep this function owned by sana_user; do not grant separate database roles direct DELETE.
BEGIN;

-- The SECURITY DEFINER owner needs narrowly scoped DELETE permission on legacy
-- compatibility tables; the application runtime role receives no direct DELETE.
DO $$
BEGIN
    IF to_regclass('public.location_history') IS NOT NULL THEN
        EXECUTE 'GRANT DELETE ON TABLE public.location_history TO sana_user';
    END IF;
    IF to_regclass('public.fleet_gpstelemetry') IS NOT NULL THEN
        EXECUTE 'GRANT DELETE ON TABLE public.fleet_gpstelemetry TO sana_user';
    END IF;
    IF to_regclass('public.fleet_gt06position') IS NOT NULL THEN
        EXECUTE 'GRANT DELETE ON TABLE public.fleet_gt06position TO sana_user';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION gps.purge_device_data(p_device_id BIGINT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, gps
AS $$
BEGIN
    -- Compatibility/legacy telemetry table lives in public, not in the gps schema.
    -- The reported FK constraint location_history_device_id_fkey is on this table.
    IF to_regclass('public.location_history') IS NOT NULL THEN
        EXECUTE 'DELETE FROM public.location_history WHERE device_id = $1' USING p_device_id;
    END IF;

    -- Django compatibility telemetry tables, when present, must also be purged.
    IF to_regclass('public.fleet_gpstelemetry') IS NOT NULL THEN
        EXECUTE 'DELETE FROM public.fleet_gpstelemetry WHERE device_id = $1' USING p_device_id;
    END IF;
    IF to_regclass('public.fleet_gt06position') IS NOT NULL THEN
        EXECUTE 'DELETE FROM public.fleet_gt06position WHERE device_id = $1' USING p_device_id;
    END IF;

    -- Delete dependents first because several GPS tables intentionally use ON DELETE RESTRICT.
    DELETE FROM gps.trip WHERE device_id = p_device_id;
    DELETE FROM gps.event WHERE device_id = p_device_id;
    DELETE FROM gps.vehicle_geofence_state WHERE device_id = p_device_id;
    DELETE FROM gps.location_history WHERE device_id = p_device_id;
    DELETE FROM gps.current_state WHERE device_id = p_device_id;
    DELETE FROM gps.raw_packet WHERE device_id = p_device_id;
END;
$$;

ALTER FUNCTION gps.purge_device_data(BIGINT) OWNER TO sana_user;
REVOKE ALL ON FUNCTION gps.purge_device_data(BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gps.purge_device_data(BIGINT) TO sana_user;

COMMIT;
