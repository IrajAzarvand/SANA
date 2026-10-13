-- Run as a PostgreSQL administrator while connected to the target SANA database,
-- after the GPS schema scripts have completed and the database is backed up.
-- This migrates any remaining objects owned by legacy SANA roles to sana_user,
-- removes their database grants, and then drops the obsolete login/owner roles.
-- It intentionally does not touch built-in PostgreSQL roles or Django user accounts.
DO $$
DECLARE
    legacy_role TEXT;
BEGIN
    FOREACH legacy_role IN ARRAY ARRAY[
        'sana_migrator',
        'sana_backend',
        'sana_gps',
        'sana_gps_test',
        'sana_owner'
    ]
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = legacy_role) THEN
            EXECUTE format('REASSIGN OWNED BY %I TO sana_user', legacy_role);
            EXECUTE format('DROP OWNED BY %I', legacy_role);
            EXECUTE format('DROP ROLE %I', legacy_role);
        END IF;
    END LOOP;
END
$$;
