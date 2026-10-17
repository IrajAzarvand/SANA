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

Road matching stores display-only coordinates in `gps.map_matched_position`.
It never changes `gps.location_history` or `gps.current_state` source coordinates.
The backend uses a recent match when available and falls back to the raw/last-valid
position when matching is disabled or no recent match exists.

For an existing database, apply `0007_neshan_map_matching.sql` as a PostgreSQL
administrator after the GPS schema has been installed:

```bash
sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 \
  -f ~/Desktop/SANA/sana-gps/sql/0007_neshan_map_matching.sql
```

The GPS service reads the optional `NESHAN_MAP_MATCHING_API_KEY` environment
variable from its systemd environment file (normally `/etc/sana-gps.env`).
Keep this service key on the server only; never put it in `sana-panel/.env`,
a `VITE_*` variable, source control, or browser requests. If the key is absent,
GPS ingestion continues normally and the map uses raw coordinates. After
provisioning the table and key, restart `sana-gps` to load the environment.
