#!/usr/bin/env bash
set -Eeuo pipefail

# Destructive development-only reset. Never run against production.
# Requires explicit SANA_ENV=development, a command-line flag, and typed confirmation.

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT_DIR" || ! -f "$ROOT_DIR/sana-backend/manage.py" || ! -f "$ROOT_DIR/sana-gps/sql/0001_gps_schema.sql" ]]; then
  echo "ERROR: Run this script from inside the SANA Git repository." >&2
  exit 1
fi

if [[ "${SANA_ENV:-}" != "development" ]]; then
  echo "ERROR: This destructive script requires SANA_ENV=development in the command environment." >&2
  echo "Example: SANA_ENV=development bash scripts/reset_dev_db.sh --confirm-reset" >&2
  exit 1
fi

if [[ "${1:-}" != "--confirm-reset" ]]; then
  echo "Refusing to continue without --confirm-reset." >&2
  echo "Usage: SANA_ENV=development bash scripts/reset_dev_db.sh --confirm-reset" >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1 || ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: sudo and PostgreSQL client tools (psql/dropdb/createdb) are required." >&2
  exit 1
fi

BACKEND_DIR="$ROOT_DIR/sana-backend"
GPS_SQL_DIR="$ROOT_DIR/sana-gps/sql"
PYTHON="$BACKEND_DIR/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "ERROR: Python not found. Create/activate the sana-backend virtual environment first." >&2
  exit 1
fi

# Read effective Django config without printing secrets.
cd "$BACKEND_DIR"
DB_NAME="$("$PYTHON" -c "from decouple import config; print(config('DB_NAME', default='sana_db'))")"
DB_USER="$("$PYTHON" -c "from decouple import config; print(config('DB_USER', default='sana_user'))")"
DB_HOST="$("$PYTHON" -c "from decouple import config; print(config('DB_HOST', default='localhost'))")"

if [[ "$DB_NAME" != "sana_db" ]]; then
  echo "ERROR: Django is configured for database '$DB_NAME', not the expected development database 'sana_db'." >&2
  exit 1
fi
if [[ "$DB_USER" != "sana_user" ]]; then
  echo "ERROR: This reset currently expects DB_USER=sana_user for Django migrations; found '$DB_USER'." >&2
  echo "Do not change DB_USER as part of this reset. Migrate the backend role separately after validating permissions." >&2
  exit 1
fi
if [[ "$DB_HOST" != "localhost" && "$DB_HOST" != "127.0.0.1" && "$DB_HOST" != "" ]]; then
  echo "ERROR: Refusing reset because Django DB_HOST is not local ('$DB_HOST')." >&2
  exit 1
fi

# Avoid dropping the DB under an actively running GPS service.
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet sana-gps.service; then
  echo "ERROR: sana-gps.service is active. Stop it manually before resetting the development database:" >&2
  echo "  sudo systemctl stop sana-gps" >&2
  echo "This script intentionally does not stop or restart services automatically." >&2
  exit 1
fi

echo
echo "DANGER: This will permanently delete ALL data in PostgreSQL database 'sana_db'."
echo "PostgreSQL roles and their existing passwords are cluster-wide and will be preserved."
echo "Django migrations and GPS tables will be recreated from repository files."
echo
read -r -p "Type exactly RESET sana_db to continue: " CONFIRM
if [[ "$CONFIRM" != "RESET sana_db" ]]; then
  echo "Confirmation did not match. Nothing was changed."
  exit 1
fi

# Get sudo credentials before doing anything destructive.
sudo -v

echo "[1/7] Ensure SANA PostgreSQL roles exist (existing passwords are not changed)..."
sudo -u postgres psql -d postgres -v ON_ERROR_STOP=1 -f /dev/stdin < "$GPS_SQL_DIR/0000_cluster_roles.sql"

echo "[2/7] Drop and recreate the development database..."
# --force terminates remaining connections (PostgreSQL 13+).
sudo -u postgres dropdb --if-exists --force sana_db
sudo -u postgres createdb --owner=sana_user sana_db

echo "[3/7] Install PostGIS and grant database connection..."
sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT CONNECT ON DATABASE sana_db TO sana_migrator, sana_backend, sana_gps;
SQL

echo "[4/7] Run Django migrations..."
"$PYTHON" manage.py migrate --noinput

echo "[5/7] Create GPS schema and tables..."
sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 -f /dev/stdin < "$GPS_SQL_DIR/0000_roles.sql"
echo "The next command will securely prompt for the existing sana_migrator password."
psql -h 127.0.0.1 -U sana_migrator -d sana_db -W -v ON_ERROR_STOP=1 -f /dev/stdin < "$GPS_SQL_DIR/0001_gps_schema.sql"

echo "[6/7] Enforce the dedicated GPS runtime role's schema access..."
# sana_backend is used only by Django's separate gps_read connection. Do not
# grant it broad access to SANA business tables in the public schema.
sudo -u postgres psql -d sana_db -v ON_ERROR_STOP=1 <<'SQL'
GRANT CONNECT ON DATABASE sana_db TO sana_backend;
GRANT USAGE ON SCHEMA gps TO sana_backend;
GRANT SELECT ON gps.current_state, gps.location_history, gps.event, gps.trip TO sana_backend;
SQL

# Fail early if the dedicated Django GPS connection has not been configured.
GPS_DB_USER="$("$PYTHON" -c "from decouple import config; print(config('GPS_DB_USER', default='sana_backend'))")"
GPS_DB_PASSWORD="$("$PYTHON" -c "from decouple import config; print(config('GPS_DB_PASSWORD', default=''))")"
if [[ "$GPS_DB_USER" != "sana_backend" ]]; then
  echo "ERROR: GPS_DB_USER must be sana_backend for the dedicated GPS connection." >&2
  exit 1
fi
if [[ -z "$GPS_DB_PASSWORD" ]]; then
  echo "ERROR: Set GPS_DB_PASSWORD in sana-backend/.env before completing this reset." >&2
  echo "Use the existing password for the PostgreSQL role sana_backend; do not print it." >&2
  exit 1
fi

echo "[7/7] Validate Django configuration and optionally create a superuser..."
"$PYTHON" manage.py check
read -r -p "Create a Django superuser now? [Y/n] " CREATE_SUPERUSER
if [[ ! "$CREATE_SUPERUSER" =~ ^([nN]|[nN][oO])$ ]]; then
  "$PYTHON" manage.py createsuperuser
fi

echo
echo "Reset completed."
echo "Database: sana_db"
echo "GPS service was not started automatically. After verifying the device/API configuration, start it manually if appropriate:"
echo "  sudo systemctl start sana-gps"
echo "Do not run this reset on a production/company database."
