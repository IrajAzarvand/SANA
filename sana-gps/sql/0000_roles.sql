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

GRANT ALL PRIVILEGES ON DATABASE sana_db TO sana_user;

-- PostGIS must be installed by a PostgreSQL administrator.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS gps AUTHORIZATION sana_user;
ALTER SCHEMA gps OWNER TO sana_user;
GRANT USAGE, CREATE ON SCHEMA gps TO sana_user;
GRANT USAGE, CREATE ON SCHEMA public TO sana_user;
