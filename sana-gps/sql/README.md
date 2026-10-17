# SANA GPS database setup

SANA uses **one PostgreSQL application login: `sana_user`** for both Django (`sana-backend`) and the GPS receiver (`sana-gps`). PostgreSQL's built-in administrator (normally `postgres`) is used only for provisioning and administration, not by either runtime service.

Apply these files in order to the target SANA PostgreSQL database:

1. As a PostgreSQL administrator, run `0000_roles.sql`. It ensures `sana_user` exists, installs PostGIS if needed, prepares the `gps` schema, and grants the required cross-schema privileges. It does not create `sana_backend`, `sana_gps`, `sana_migrator`, or `sana_owner`.
2. Set the `sana_user` password interactively or through your local secret-management process. Do not commit passwords or put them in SQL files.
3. Run `0001_gps_schema.sql` as a PostgreSQL administrator; the script switches to `sana_user` while creating GPS objects.
4. Run `0002_detected_protocol_registration.sql` as a PostgreSQL administrator.
5. Configure Django's ignored local/server environment file with `DB_USER=sana_user`; configure `/etc/sana-gps.env` with `SANA_GPS_DB_USER=sana_user`. Both must use the same database name, host/port as appropriate, and the same secret for `sana_user`.

The database login is separate from Django's application-level users and roles. Do not confuse the PostgreSQL role `sana_user` with the SANA site-admin account.

## Removing legacy PostgreSQL roles

`0004_remove_legacy_roles.sql` is a cleanup script for installations that still contain old SANA roles. Back up the database first. Run the cleanup in **each database** where the legacy roles may own objects or have grants, then confirm no dependencies remain before dropping the cluster-wide roles. PostgreSQL roles are cluster-wide and are not removed by dropping a database. Never remove built-in roles or unrelated roles.

The integration test workflow checks that `sana_owner`, `sana_migrator`, `sana_backend`, `sana_gps`, and `sana_gps_test` do not remain after provisioning/cleanup.

The migration references the Django tables `public.fleet_device`, `public.fleet_devicemodel`, and `public.fleet_vehicle`; verify those names in the target database before applying.

## Optional Neshan road matching

Road-matched coordinates are stored on the existing GPS rows:
- `gps.current_state` holds the matched position for the current/last-valid fix used by the live map.
- `gps.location_history` holds the matched position for each historical fix, so reports can reuse cached matches.
Raw latitude/longitude values are never overwritten. The live map falls back to raw/last-valid coordinates until the exact current fix has a match.

For databases where migration `0007_neshan_map_matching.sql` has already been applied, apply `0008_store_map_matches_in_existing_tables.sql` to move any existing matches to the existing tables and drop the temporary `gps.map_matched_position` table. Fresh installations should apply the SQL migrations in order.

The GPS service reads the optional `NESHAN_MAP_MATCHING_API_KEY` environment
variable from its systemd environment file (normally `/etc/sana-gps.env`).
Keep this service key on the server only; never put it in `sana-panel/.env`,
a `VITE_*` variable, source control, or browser requests. If the key is absent,
GPS ingestion continues normally and the map uses raw coordinates. After
applying the schema migrations, restart `sana-gps` to load the environment.

Historical-report matching is not yet an on-demand report workflow: the current
background worker only processes recent fixes. The report implementation should
process missing matches for the selected time range in ordered batches (with
overlap points at batch boundaries), persist results to `gps.location_history`,
and clearly identify any points that could not be matched rather than silently
claiming every point is exact.
