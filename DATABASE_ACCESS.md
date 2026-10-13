# SANA database access (single application login)

SANA uses one PostgreSQL application login: `sana_user`. Django and the GPS receiver use this same database role. Do not create separate PostgreSQL logins for organization managers, branch managers, personal customers, the GPS service, or Django's migration process.

## Two different kinds of accounts

- **PostgreSQL `postgres`**: database administrator used for initial provisioning, PostGIS installation, and database maintenance. Do not use it in the application's environment files.
- **PostgreSQL `sana_user`**: the only normal application database login for Django and GPS ingestion.
- **SANA site administrator**: a Django account created with `python manage.py createsuperuser`. It is not the PostgreSQL `postgres` account.
- **Company, branch, and personal users**: ordinary Django accounts. Their device visibility and allowed actions must be enforced by backend querysets and DRF permissions, not by creating PostgreSQL users.

The application role is intentionally not a PostgreSQL superuser. It owns the SANA database objects and has the access needed inside `sana_db`; PostgreSQL-wide administration remains with `postgres`.

## Local development credentials

The existing local-development convention is:

```dotenv
DB_NAME=sana_db
DB_USER=sana_user
DB_PASSWORD=sana_password_123
DB_HOST=localhost
DB_PORT=5432
```

The password shown here is for local development only. Set a different strong password on any shared or production server, and configure the same password for the GPS service without committing secrets to Git.

## Fresh database setup

Run commands from the repository root, adjusting paths if needed.

1. Create the role/database and install PostGIS as a PostgreSQL administrator. If `sana_db` already exists, do not drop it until you have a backup.

   ```sql
   -- Run as postgres in psql:
   CREATE ROLE sana_user LOGIN PASSWORD 'sana_password_123'
       NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
   CREATE DATABASE sana_db OWNER sana_user;
   ```

   If the role or database already exists, do not rerun the `CREATE` statements; normalize the existing role and database owner instead. Then connect to `sana_db` as an administrator and run:

   ```sql
   ALTER DATABASE sana_db OWNER TO sana_user;
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

2. Provision the GPS schema and ensure the single application role is configured:

   ```bash
   sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 -f sana-gps/sql/0000_roles.sql
   ```

3. Run Django migrations using the `sana_user` credentials in `sana-backend/.env`:

   ```bash
   cd sana-backend
   python manage.py migrate
   ```

4. Create the SANA site-administrator account if one does not exist:

   ```bash
   python manage.py createsuperuser
   ```

5. Create GPS tables and the device-purge function. Run these scripts as the PostgreSQL administrator; they switch to `sana_user` when creating GPS objects.

   ```bash
   cd ..
   sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 -f sana-gps/sql/0001_gps_schema.sql
   sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 -f sana-gps/sql/0003_purge_device_telemetry.sql
   ```

6. After confirming the new schema works and taking a backup, remove the legacy database roles. This script transfers any remaining owned objects to `sana_user`, removes old grants, and drops only the legacy `sana_*` roles:

   ```bash
   sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 -f sana-gps/sql/0004_remove_legacy_roles.sql
   ```

7. Configure the GPS service to use the same role:

   ```dotenv
   SANA_GPS_DB_NAME=sana_db
   SANA_GPS_DB_USER=sana_user
   SANA_GPS_DB_PASSWORD=sana_password_123
   SANA_GPS_DB_HOST=127.0.0.1
   SANA_GPS_DB_PORT=5432
   ```

   On the server, keep the service's environment file (for example, `/etc/sana-gps.env`) private and use the same strong password configured for `sana_user`.

## Important

- Do not create PostgreSQL roles named `sana_gps`, `sana_gps_test`, `sana_backend`, `sana_migrator`, or `sana_owner` for a fresh installation. The SQL setup no longer requires them.
- The legacy-role cleanup script is explicit and destructive with respect to those PostgreSQL roles: run it only after backing up the database, confirming the new schema works, and checking that no old service or deployment still uses those logins.
- Do not grant PostgreSQL superuser status to `sana_user`.
- Database access is not the customer authorization model. Django must limit each company manager, branch manager, and personal user to their own devices and permitted read-only actions; only the SANA site administrator may perform global device-management operations.
