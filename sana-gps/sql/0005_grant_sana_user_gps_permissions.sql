-- Repair runtime privileges for the single SANA database role.
-- Run as a PostgreSQL administrator while connected to the SANA database.
-- Idempotent: grants permissions only; does not drop roles, change ownership,
-- delete data, or modify Django application users.

GRANT USAGE ON SCHEMA gps TO sana_user;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA gps
    TO sana_user;

GRANT USAGE, SELECT, UPDATE
    ON ALL SEQUENCES IN SCHEMA gps
    TO sana_user;

-- Keep future GPS objects accessible when they are created by sana_user.
ALTER DEFAULT PRIVILEGES FOR ROLE sana_user IN SCHEMA gps
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sana_user;

ALTER DEFAULT PRIVILEGES FOR ROLE sana_user IN SCHEMA gps
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO sana_user;
