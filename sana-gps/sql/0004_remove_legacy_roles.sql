-- Run as a PostgreSQL administrator in EACH database that may contain
-- objects owned by legacy SANA roles or grants to/from them.
-- Back up the database first. This script only cleans the CURRENT database;
-- it deliberately does not drop cluster-wide roles. After running this in every
-- relevant database, run 0006_drop_legacy_cluster_roles.sql once.
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
        END IF;
    END LOOP;
END
$$;
