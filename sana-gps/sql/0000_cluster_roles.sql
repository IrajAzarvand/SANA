-- Cluster-wide SANA roles for repeatable development database rebuilds.
-- Run as a PostgreSQL administrator while connected to any existing database.
-- Passwords are deliberately not created or changed here: existing passwords
-- survive database drops because PostgreSQL roles are cluster-wide.

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

-- Normalize security attributes without changing any role password.
ALTER ROLE sana_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_backend LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE sana_gps LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

GRANT sana_owner TO sana_migrator;
