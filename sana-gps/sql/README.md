# SANA GPS database setup

Apply these files in order to the existing SANA PostgreSQL database.

1. As a PostgreSQL administrator, run `0000_roles.sql`. It creates the four separated roles, installs PostGIS if needed, creates the `gps` schema owned by `sana_owner`, and grants only the required cross-schema FK privileges.
2. Set distinct strong passwords interactively for `sana_migrator`, `sana_backend`, and `sana_gps`. Do not commit passwords or put them in SQL files.
3. Run `0001_gps_schema.sql` while connected as `sana_migrator`. The role can assume `sana_owner` only for controlled schema changes.
4. Configure the GPS runtime environment with `SANA_GPS_DB_USER=sana_gps` and the password set for that role. The application intentionally rejects other runtime DB usernames.
5. Configure Django with `sana_backend`; never use `sana_owner` or `sana_migrator` as an application runtime account.

The migration references the repository's actual Django tables `public.fleet_device`, `public.fleet_devicemodel`, and `public.fleet_vehicle`. Verify those table names in the target database before applying.

The GPS runtime receives no DDL permissions, cannot mutate `fleet_device`, cannot delete telemetry history, and has no access to `gps.raw_packet` from the backend role. Do not apply this migration from application startup.
