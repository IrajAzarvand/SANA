-- Run as a PostgreSQL administrator while connected to sana_db.
-- SANA uses one database login (sana_user) for Django and the GPS receiver.
-- Keep postgres for database provisioning/administration only; it is not an
-- application login. The Django site-admin account is separate from PostgreSQL.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_user') THEN
        CREATE ROLE sana_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
END
$$;

-- Normalize the single application role. Its password is set during local/server
-- provisioning, not embedded in version-controlled SQL.
ALTER ROLE sana_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;

DO $ BEGIN
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO sana_user', current_database());
END $;

-- PostGIS must be installed by a PostgreSQL administrator.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS gps AUTHORIZATION sana_user;
ALTER SCHEMA gps OWNER TO sana_user;
GRANT USAGE, CREATE ON SCHEMA gps TO sana_user;
GRANT USAGE, CREATE ON SCHEMA public TO sana_user;

-- In a fresh SANA install, Django-created business tables are owned by sana_user.
-- These conditional grants also let the GPS schema setup run in isolated tests or
-- upgrades where representative public tables were created by the administrator.
DO $
BEGIN
    IF to_regclass('public.fleet_device') IS NOT NULL THEN
        EXECUTE 'GRANT REFERENCES (id) ON public.fleet_device TO sana_user';
        EXECUTE 'GRANT SELECT (id, protocol, device_model_id) ON public.fleet_device TO sana_user';
        EXECUTE 'GRANT UPDATE (protocol) ON public.fleet_device TO sana_user';
    END IF;
    IF to_regclass('public.fleet_devicemodel') IS NOT NULL THEN
        EXECUTE 'GRANT SELECT (id, protocol) ON public.fleet_devicemodel TO sana_user';
    END IF;
    IF to_regclass('public.fleet_vehicle') IS NOT NULL THEN
        EXECUTE 'GRANT REFERENCES (id) ON public.fleet_vehicle TO sana_user';
    END IF;
END $;
