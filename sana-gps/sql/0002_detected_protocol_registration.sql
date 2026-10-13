-- SANA GPS migration 0002: narrowly-scoped automatic device protocol registration.
-- Run as a PostgreSQL administrator after sql/0001_gps_schema.sql.
--
-- The GPS receiver and Django use the same sana_user database login. The function
-- keeps protocol-registration logic in one place; application authorization remains in Django.

BEGIN;

GRANT SELECT (id, protocol, device_model_id)
    ON public.fleet_device TO sana_user;
GRANT SELECT (id, protocol)
    ON public.fleet_devicemodel TO sana_user;
GRANT UPDATE (protocol)
    ON public.fleet_device TO sana_user;

CREATE OR REPLACE FUNCTION gps.register_detected_device_protocol(
    p_device_id BIGINT,
    p_detected_protocol TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    normalized_protocol TEXT;
    affected_device_id BIGINT;
BEGIN
    normalized_protocol := lower(btrim(COALESCE(p_detected_protocol, '')));
    IF normalized_protocol = '' THEN
        RETURN FALSE;
    END IF;

    UPDATE public.fleet_device AS d
    SET protocol = CASE
        WHEN COALESCE(NULLIF(btrim(d.protocol), ''), '') = ''
            THEN normalized_protocol
        ELSE d.protocol
    END
    WHERE d.id = p_device_id
      AND (
          COALESCE(NULLIF(btrim(d.protocol), ''), '') = ''
          OR lower(btrim(d.protocol)) = normalized_protocol
      )
      AND (
          d.device_model_id IS NULL
          OR EXISTS (
              SELECT 1
              FROM public.fleet_devicemodel AS dm
              WHERE dm.id = d.device_model_id
                AND (
                    COALESCE(NULLIF(btrim(dm.protocol), ''), '') = ''
                    OR lower(btrim(dm.protocol)) = normalized_protocol
                )
          )
      )
    RETURNING d.id INTO affected_device_id;

    RETURN FOUND;
END;
$function$;

ALTER FUNCTION gps.register_detected_device_protocol(BIGINT, TEXT)
    OWNER TO sana_user;

REVOKE ALL ON FUNCTION gps.register_detected_device_protocol(BIGINT, TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gps.register_detected_device_protocol(BIGINT, TEXT)
    TO sana_user;

COMMIT;
