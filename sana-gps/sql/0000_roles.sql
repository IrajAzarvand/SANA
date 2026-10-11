-- Run once as a PostgreSQL administrator. Set passwords out-of-band afterwards.
-- Runtime roles are intentionally not superusers and cannot create databases/roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_owner') THEN
        CREATE ROLE sana_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_migrator') THEN
        CREATE ROLE sana_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_backend') THEN
        CREATE ROLE sana_backend LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_gps') THEN
        CREATE ROLE sana_gps LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END
$$;

ALTER ROLE sana_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_backend LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_gps LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

CREATE EXTENSION IF NOT EXISTS postgis;

-- Create/normalize the GPS schema as the database administrator so the owner
-- role does not need CREATE privilege on the entire database.
CREATE SCHEMA IF NOT EXISTS gps AUTHORIZATION sana_owner;
ALTER SCHEMA gps OWNER TO sana_owner;
GRANT USAGE, CREATE ON SCHEMA gps TO sana_owner, sana_migrator;
GRANT USAGE ON SCHEMA gps TO sana_gps, sana_backend;

-- Permit the GPS object owner to declare cross-schema foreign keys without
-- granting it SELECT or mutation access to business rows.
GRANT USAGE ON SCHEMA public TO sana_owner;
GRANT REFERENCES (id) ON public.fleet_device TO sana_owner;
GRANT REFERENCES (id) ON public.fleet_vehicle TO sana_owner;
GRANT SELECT (id, imei, management_status, protocol, device_model_id)
    ON public.fleet_device TO sana_gps;
GRANT SELECT (id, manufacturer, name, code, protocol)
    ON public.fleet_devicemodel TO sana_gps;

-- Only the migrator may assume object-owner authority for controlled DDL.
GRANT sana_owner TO sana_migrator;

-- After running this file as an administrator, set strong, distinct passwords
-- interactively (do not put them in source control):
--   \password sana_migrator
--   \password sana_backend
--   \password sana_gps
