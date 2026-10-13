-- Cluster-wide SANA PostgreSQL role for repeatable development database rebuilds.
-- Run as a PostgreSQL administrator while connected to an existing database.
-- The only application login is sana_user; backend and GPS share it.
-- This script never creates or changes legacy roles and does not set passwords.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sana_user') THEN
        CREATE ROLE sana_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
END
$$;

ALTER ROLE sana_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
