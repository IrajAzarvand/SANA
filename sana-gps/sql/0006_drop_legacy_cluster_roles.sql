-- Run once as a PostgreSQL administrator, after 0004_remove_legacy_roles.sql
-- has been run in EVERY database that may contain objects owned by legacy roles.
-- This removes only obsolete SANA roles; built-in PostgreSQL roles are untouched.
-- DROP ROLE intentionally fails if any dependency remains anywhere in the cluster.
DO $$
DECLARE
    legacy_role TEXT;
    member_role TEXT;
    granted_role TEXT;
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
            -- Remove memberships where the legacy role was granted to another role.
            FOR member_role IN
                SELECT member.rolname
                FROM pg_auth_members am
                JOIN pg_roles granted ON granted.oid = am.roleid
                JOIN pg_roles member ON member.oid = am.member
                WHERE granted.rolname = legacy_role
            LOOP
                EXECUTE format('REVOKE %I FROM %I', legacy_role, member_role);
            END LOOP;

            -- Remove memberships where the legacy role was itself a member.
            FOR granted_role IN
                SELECT granted.rolname
                FROM pg_auth_members am
                JOIN pg_roles granted ON granted.oid = am.roleid
                JOIN pg_roles member ON member.oid = am.member
                WHERE member.rolname = legacy_role
            LOOP
                EXECUTE format('REVOKE %I FROM %I', granted_role, legacy_role);
            END LOOP;

            EXECUTE format('DROP ROLE %I', legacy_role);
        END IF;
    END LOOP;
END
$$;
