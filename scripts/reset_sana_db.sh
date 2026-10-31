#!/usr/bin/env bash
# SANA - بازسازی کامل دیتابیس و جداول Django/GPS
# اجرا از هر مسیر: bash ~/Desktop/SANA/scripts/reset_sana_db.sh
#
# برای جلوگیری از اتصال هنگام بازسازی، Backend و GPS متوقف می‌شوند؛ پس از موفقیت آزمون‌ها هر دو دوباره راه‌اندازی می‌شوند.
# مجوز پایش زنده شبکه (tcpdump wrapper و sudoers) تنظیم سیستم‌عامل است و این
# اسکریپت آن را ایجاد، حذف یا تغییر نمی‌دهد.
#
# هشدار: دیتابیس sana_db کاملاً حذف و دوباره ساخته می‌شود.
# همه داده‌ها، کاربران و سوپریوزر قبلی آن از بین می‌روند.

set -Eeuo pipefail
IFS=$'\n\t'

# Resolve the repository root whether this script is run from the repository root
# or from scripts/reset_sana_db.sh. SANA_ROOT can explicitly override discovery.
if [[ -n "${SANA_ROOT:-}" ]]; then
    ROOT="$(cd -- "$SANA_ROOT" && pwd)"
else
    SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -d "$SCRIPT_DIR/sana-backend" && -d "$SCRIPT_DIR/sana-gps" ]]; then
        ROOT="$SCRIPT_DIR"
    elif [[ -d "$SCRIPT_DIR/../sana-backend" && -d "$SCRIPT_DIR/../sana-gps" ]]; then
        ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
    else
        echo "❌ ریشه پروژه تشخیص داده نشد؛ SANA_ROOT را روی مسیر ریشه SANA تنظیم کن." >&2
        exit 1
    fi
fi
BACKEND="$ROOT/sana-backend"
GPS="$ROOT/sana-gps"
MANAGE="$BACKEND/manage.py"
PYTHON="$BACKEND/venv/bin/python"
SQL_DIR="$GPS/sql"
ROLE_SQL="0000_roles.sql"

DB_NAME="${SANA_DB_NAME:-sana_db}"
DB_OWNER="${SANA_DB_OWNER:-sana_user}"
[[ "$DB_OWNER" == "sana_user" ]] || { echo "❌ در معماری فعلی، SANA_DB_OWNER باید sana_user باشد." >&2; exit 1; }

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reset-sana-$(date +%Y%m%d-%H%M%S).log"

STEP="آماده‌سازی"
SERVICE_STOPPED=0
BACKEND_STOPPED=0
START_TIME="$(date +%s)"
RUN_SUCCEEDED=0

exec > >(tee -a "$LOG_FILE") 2>&1

on_exit() {
    rc=$?
    if [[ "$rc" -ne 0 && "$RUN_SUCCEEDED" -ne 1 ]]; then
        echo
        echo "❌ اجرای اسکریپت ناموفق بود."
        echo "آخرین مرحله: $STEP"
        echo "کد خروج: $rc"
        echo "گزارش کامل: $LOG_FILE"

        if [[ "$SERVICE_STOPPED" == "1" ]]; then
            sudo systemctl stop sana-gps >/dev/null 2>&1 || true
            echo "سرویس GPS متوقف نگه داشته شد."
        fi

        if [[ "$BACKEND_STOPPED" == "1" ]]; then
            sudo systemctl stop sana-backend >/dev/null 2>&1 || true
            echo "سرویس Backend متوقف نگه داشته شد تا وضعیت دیتابیس بررسی شود."
        fi
    fi
}
trap on_exit EXIT

step() {
    STEP="$1"
    echo
    echo "============================================================"
    echo "▶ $STEP"
    echo "============================================================"
}

die() {
    echo "❌ $*" >&2
    exit 1
}

# Ensure the Traccar credentials are available to both the GPS worker and Django.
# Secrets are written only to the root-owned /etc/sana-gps.env, never committed here.
TRACCAR_ENV_FILE="/etc/sana-gps.env"
BACKEND_ENV_DROPIN="/etc/systemd/system/sana-backend.service.d/traccar-env.conf"

read_env_value() {
    local key="$1"
    sudo grep -E "^[[:space:]]*${key}=" "$TRACCAR_ENV_FILE" 2>/dev/null \
        | tail -n 1 | sed -E "s/^[[:space:]]*${key}=//" || true
}

ensure_env_value() {
    local key="$1"
    local value="$2"
    [[ -n "$value" ]] || return 1
    printf '%s=%s\n' "$key" "$value" | sudo tee -a "$TRACCAR_ENV_FILE" >/dev/null
}

configure_traccar_credentials() {
    step "بررسی تنظیمات اتصال Traccar برای Backend و GPS"

    if ! sudo test -f "$TRACCAR_ENV_FILE"; then
        sudo install -o root -g root -m 600 /dev/null "$TRACCAR_ENV_FILE"
    fi

    local username password
    echo "برای اتصال Backend به Traccar، مشخصات حساب را وارد کن."
    read -r -p "نام کاربری Traccar: " username
    [[ -n "$username" ]] || die "نام کاربری Traccar نمی‌تواند خالی باشد."
    read -r -s -p "رمز عبور Traccar: " password
    echo
    [[ -n "$password" ]] || die "رمز عبور Traccar نمی‌تواند خالی باشد."

    # Store both Django-standard and GPS-worker names in the protected env file.
    # Remove previous assignments first so the new interactive values take effect.
    local tmp_env
    tmp_env="$(mktemp)"
    sudo awk '
        !/^[[:space:]]*(TRACCAR_API_USERNAME|TRACCAR_API_PASSWORD|SANA_GPS_TRACCAR_API_USERNAME|SANA_GPS_TRACCAR_API_PASSWORD)=/
    ' "$TRACCAR_ENV_FILE" > "$tmp_env"
    printf '%s=%s\n' \
        "TRACCAR_API_USERNAME" "$username" \
        "TRACCAR_API_PASSWORD" "$password" \
        "SANA_GPS_TRACCAR_API_USERNAME" "$username" \
        "SANA_GPS_TRACCAR_API_PASSWORD" "$password" >> "$tmp_env"
    sudo install -o root -g root -m 600 "$tmp_env" "$TRACCAR_ENV_FILE"
    rm -f "$tmp_env"

    sudo chown root:root "$TRACCAR_ENV_FILE"
    sudo chmod 600 "$TRACCAR_ENV_FILE"

    # Have systemd expose this protected file to the Django backend service.
    sudo install -d -o root -g root -m 755 "$(dirname "$BACKEND_ENV_DROPIN")"
    printf '[Service]\nEnvironmentFile=%s\n' "$TRACCAR_ENV_FILE" \
        | sudo tee "$BACKEND_ENV_DROPIN" >/dev/null
    sudo chown root:root "$BACKEND_ENV_DROPIN"
    sudo chmod 644 "$BACKEND_ENV_DROPIN"
    sudo systemctl daemon-reload

    echo "✅ متغیرهای TRACCAR_API_* برای Backend بررسی شدند؛ مقادیر محرمانه نمایش داده نمی‌شوند."
}

echo "SANA - Database Reset (Backend and GPS restart after successful checks)"
echo "زمان: $(date --iso-8601=seconds)"
echo "ریشه پروژه: $ROOT"
echo "دیتابیس: $DB_NAME"
echo "مالک دیتابیس: $DB_OWNER"
echo "گزارش اجرا: $LOG_FILE"

# بررسی اولیه مسیرها و فایل‌های لازم
[[ "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] ||
    die "نام دیتابیس نامعتبر است؛ فقط حروف انگلیسی، عدد و زیرخط مجاز است."
[[ "$DB_OWNER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] ||
    die "نام نقش PostgreSQL نامعتبر است."

[[ -d "$BACKEND" ]] || die "پوشه sana-backend پیدا نشد."
[[ -d "$GPS" ]] || die "پوشه sana-gps پیدا نشد."
[[ -f "$MANAGE" ]] || die "فایل manage.py پیدا نشد."
[[ -x "$PYTHON" ]] || die "Python محیط مجازی پیدا نشد."
[[ -d "$SQL_DIR" ]] || die "پوشه sql پیدا نشد."
[[ -f "$SQL_DIR/$ROLE_SQL" ]] || die "فایل SQL نقش‌ها پیدا نشد: $SQL_DIR/$ROLE_SQL"

command -v sudo >/dev/null || die "sudo نصب نیست."
command -v psql >/dev/null || die "psql پیدا نشد."
command -v systemctl >/dev/null || die "systemctl پیدا نشد."

# 0000_roles.sql پیش از migrationهای Django اجرا می‌شود. پس از آن فقط یک
# schema SQL رسمی اجرا می‌شود که جدول‌های Neshan Map Matching را می‌سازد و
# ساختارهای خام/تاریخچه GPS قدیمی را باقی نمی‌گذارد.
# Migration تجمیعی fleet (0003_squashed_0015_traccar_authoritative) مسیر نصب تازه را
# مستقیماً به schema نهایی می‌رساند و جدول‌های telemetry قدیمی را ایجاد نمی‌کند.
# Migrationهای جایگزین‌شده برای تشخیص دیتابیس‌های قدیمی/نیمه‌ارتقایافته حفظ می‌شوند؛
# Django فقط در صورت نیاز از زنجیره تاریخی آن‌ها استفاده خواهد کرد.
SQL_FILES=(
    "0001_traccar_authoritative_schema.sql"
)

for file in "${SQL_FILES[@]}"; do
    [[ -f "$SQL_DIR/$file" ]] ||
        die "فایل SQL لازم پیدا نشد: $SQL_DIR/$file"
done

echo
echo "⚠️ هشدار: این عملیات دیتابیس '$DB_NAME' را کامل حذف می‌کند."
echo "تمام کاربران، داده‌های GPS و اطلاعات داخل آن پاک خواهند شد."
echo "تمام جدول‌های دیتابیس همراه خود دیتابیس حذف و بر اساس migrationهای فعلی و SQLهای GPS بازسازی می‌شوند."
echo "معماری GPS: Traccar تنها مرجع داده خام است؛ سانا فقط نتایج Neshan و نشست‌های فعال نقشه را نگه می‌دارد. دریافت آزمایشی پورت صرفاً ابزار موقت ادمین است."
echo "تنظیم مجوز پایش زنده شبکه در لینوکس مستقل است و در این عملیات دست‌کاری نمی‌شود."
echo

read -r -p "برای تأیید، نام دیتابیس را دقیقاً وارد کن [$DB_NAME]: " CONFIRM
[[ "$CONFIRM" == "$DB_NAME" ]] ||
    die "تأیید صحیح نبود؛ دیتابیس حذف نشد."

# Validate/prepare Traccar API environment before stopping services or dropping the DB.
configure_traccar_credentials

# بررسی اعتبار sudo پیش از توقف سرویس یا هر عملیات مخرب
step "آماده‌سازی دسترسی مدیریتی"
sudo -v

# ۱. توقف سرویس GPS و Backend برای جلوگیری از اتصال هنگام بازسازی دیتابیس
step "۱/۱۲ - توقف سرویس‌های GPS و Backend"

sudo systemctl stop sana-gps
SERVICE_STOPPED=1
if systemctl is-active --quiet sana-gps; then
    die "سرویس GPS هنوز فعال است."
fi
echo "✅ سرویس GPS متوقف است."

sudo systemctl stop sana-backend
BACKEND_STOPPED=1
if systemctl is-active --quiet sana-backend; then
    die "سرویس Backend هنوز فعال است."
fi
echo "✅ سرویس Backend متوقف است."

# ۲. بررسی نقش PostgreSQL
step "۲/۱۲ - بررسی نقش PostgreSQL"

ROLE_EXISTS="$(
    sudo -u postgres psql -X -d postgres -At \
        -v role_name="$DB_OWNER" <<'SQL'
SELECT count(*) FROM pg_roles WHERE rolname = :'role_name';
SQL
)" 

[[ "$ROLE_EXISTS" == "1" ]] ||
    die "نقش PostgreSQL '$DB_OWNER' وجود ندارد."

echo "✅ نقش $DB_OWNER موجود است."

# ۳. حذف و ساخت دیتابیس
step "۳/۱۲ - بازسازی دیتابیس"

sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
    -d postgres -v dbname="$DB_NAME" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'dbname'
  AND pid <> pg_backend_pid();

SELECT format('DROP DATABASE IF EXISTS %I', :'dbname') \gexec
SQL

sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
    -d postgres \
    -v dbname="$DB_NAME" \
    -v dbowner="$DB_OWNER" <<'SQL'
SELECT format(
    'CREATE DATABASE %I OWNER %I',
    :'dbname',
    :'dbowner'
) \gexec
SQL

echo "✅ دیتابیس جدید ساخته شد."

# ۴. فعال‌سازی PostGIS
step "۴/۱۲ - فعال‌سازی PostGIS"

sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
    -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "✅ PostGIS فعال است."

# ۵. آماده‌سازی نقش و schema پایه پیش از migrationهای Django.
step "۵/۱۲ - آماده‌سازی نقش PostgreSQL"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d "$DB_NAME" < "$SQL_DIR/$ROLE_SQL"
echo "✅ نقش sana_user و schema پایه آماده شدند."

# ۶. اجرای migrationهای Django؛ Django وابستگی‌ها را از graph واقعی می‌خواند.
step "۶/۱۲ - اجرای migrationهای Django"
cd "$BACKEND"
"$PYTHON" "$MANAGE" migrate --noinput
echo "✅ اجرای migrationها کامل شد."

# پرکردن کاتالوگ مدل‌های قابل انتخاب Traccar بعد از ساخت جدول‌ها و پیش از آزمون نهایی.
# در صورت شکست دریافت یا ذخیره کاتالوگ، set -e مانع ادامه بازسازی و راه‌اندازی سرویس‌ها می‌شود.
step "۷/۱۲ - پرکردن کاتالوگ مدل‌های Traccar"
cd "$BACKEND"
"$PYTHON" "$MANAGE" sync_traccar_device_catalog
echo "✅ کاتالوگ مدل‌های Traccar همگام شد."

# ۶. بررسی Django و وضعیت migrationها
step "۸/۱۲ - آزمون تنظیمات Django"

"$PYTHON" "$MANAGE" check

"$PYTHON" "$MANAGE" makemigrations --check --dry-run

echo "✅ بررسی Django موفق بود."

# ۷. ساخت schema و تنظیمات GPS
step "۹/۱۲ - اجرای SQLهای GPS"

cd "$GPS"

for file in "${SQL_FILES[@]}"; do
    echo
    echo "▶ اجرای $file"

    # Read the SQL as the invoking user, then pass it over stdin to psql.
    # postgres may not have permission to traverse the project under /home/iraj.
    sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
        -d "$DB_NAME" \
        < "$SQL_DIR/$file"
done

echo "✅ SQLهای GPS اجرا شدند."

# ۸. آزمون اتصال، وجود جداول و دسترسی به جداول مشترک
step "۱۰/۱۲ - آزمون دیتابیس و جداول"

cd "$BACKEND"

EXPECTED_DB="$DB_NAME" EXPECTED_USER="$DB_OWNER" \
"$PYTHON" "$MANAGE" shell -c '
import os
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.conf import settings

expected_db = os.environ["EXPECTED_DB"]
expected_user = os.environ["EXPECTED_USER"]

# Confirm that Django applied every leaf migration currently present in the repo.
loader = MigrationLoader(connection)
applied = loader.applied_migrations
unapplied_leaves = [
    node for node in loader.graph.leaf_nodes()
    if node not in applied
]
assert not unapplied_leaves, f"Unapplied migration leaves: {unapplied_leaves}"
print("Django migration leaves:", sorted(loader.graph.leaf_nodes()))
if not settings.TRACCAR_API_USERNAME or not settings.TRACCAR_API_PASSWORD:
    print("WARNING: TRACCAR_API_USERNAME/PASSWORD are not configured; live map and reports will return 503.")
else:
    print("Traccar API credentials are configured for the Django backend.")

required_tables = [
    "public.fleet_device",
    "public.fleet_devicemodel",
    "gps.map_matching_watchers",
    "gps.map_matched_position",
]

with connection.cursor() as cursor:
    cursor.execute("SELECT current_database(), current_user")
    db, user = cursor.fetchone()
    print("Database:", db)
    print("Database user:", user)
    assert db == expected_db, f"Wrong database: {db}"
    assert user == expected_user, f"Wrong database user: {user}"

    for table in required_tables:
        cursor.execute("SELECT to_regclass(%s)", [table])
        exists = cursor.fetchone()[0]
        print(f"{table}: {exists}")
        assert exists is not None, f"Required table is missing: {table}"

    forbidden_tables = [
        "public.fleet_gpstelemetry",
        "public.fleet_unknowngpsdata",
        "gps.raw_packet",
        "gps.location_history",
        "gps.current_state",
        "gps.event",
        "gps.trip",
        "gps.geofence",
        "gps.geofence_version",
        "gps.geofence_assignment",
        "gps.vehicle_geofence_state",
        "gps.traccar_unknown_device",
    ]
    for table in forbidden_tables:
        cursor.execute("SELECT to_regclass(%s)", [table])
        exists = cursor.fetchone()[0]
        print(f"Legacy table must be absent: {table} -> {exists}")
        assert exists is None, f"Obsolete duplicate GPS table still exists: {table}"

    # Validate columns that were added by the latest SQL schema changes, not just
    # table names. This catches a partially applied or outdated GPS schema.
    required_columns = {
        # Final Django schema after fleet migrations through 0015.
        "public.fleet_device": {
            "imei", "device_model_id", "protocol", "organization_id", "owner_user_id",
            "branch_id", "current_holder_organization_id", "current_holder_user_id",
            "vehicle_id", "management_status", "installed_at", "created_at", "updated_at",
        },
        "public.fleet_devicemodel": {
            "manufacturer", "name", "code", "protocol", "port", "traccar_version",
            "source_url", "is_verified", "created_at",
        },
        "gps.map_matching_watchers": {
            "session_id", "user_id", "expires_at", "updated_at",
        },
        "gps.map_matched_position": {
            "traccar_position_id", "traccar_device_id", "device_id", "device_time",
            "matched_latitude", "matched_longitude", "matched_geom", "match_provider", "matched_at",
        },
    }
    for table, expected_columns in required_columns.items():
        schema, table_name = table.split(".", 1)
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """, [schema, table_name])
        actual_columns = {row[0] for row in cursor.fetchall()}
        missing = expected_columns - actual_columns
        assert not missing, f"{table} missing columns: {sorted(missing)}"
        print(f"Columns OK: {table} ({len(expected_columns)} checked)")

    # Exercise SELECT privileges using the actual application database login.
    for table in (
        "gps.map_matching_watchers",
        "gps.map_matched_position",
    ):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"SELECT access OK: {table}; rows={cursor.fetchone()[0]}")

    cursor.execute("SELECT postgis_full_version()")
    print("PostGIS:", cursor.fetchone()[0])

print("✅ Database, Django migrations, current GPS schema and privileges passed.")
'

echo "✅ جداول و دسترسی‌های اصلی تأیید شدند."

# ۹. ساخت سوپریوزر
step "۱۱/۱۲ - ساخت سوپریوزر سایت"

echo "نام کاربری، ایمیل و رمز را در پرسش‌های Django وارد کن."
echo "رمز در فایل اسکریپت یا گزارش ذخیره نمی‌شود."

"$PYTHON" "$MANAGE" createsuperuser

echo "✅ مرحله ساخت سوپریوزر پایان یافت."

# ۱۰. راه‌اندازی سرویس‌ها فقط پس از موفقیت آزمون دیتابیس و ساخت سوپریوزر
step "۱۲/۱۲ - راه‌اندازی و تأیید نهایی سرویس‌ها"

echo "راه‌اندازی Backend Django..."
sudo systemctl start sana-backend
if ! systemctl is-active --quiet sana-backend; then
    die "سرویس Backend پس از راه‌اندازی فعال نشد."
fi
echo "✅ سرویس Backend فعال است."

echo "راه‌اندازی سرویس GPS..."
sudo systemctl start sana-gps
if ! systemctl is-active --quiet sana-gps; then
    die "سرویس GPS پس از راه‌اندازی فعال نشد."
fi
echo "✅ سرویس GPS فعال است."

# سرویس‌ها ممکن است چند ثانیه بعد از systemctl start پورت را باز کنند.
# برای جلوگیری از خطای کاذب، برای هر پورت تا 30 ثانیه منتظر می‌مانیم.
for port in 8000; do
    port_ready=0
    for attempt in {1..30}; do
        if sudo ss -H -lntup | grep -Eq ":${port}([[:space:]]|$)"; then
            port_ready=1
            echo "✅ پورت ${port} در حال شنود است."
            break
        fi
        sleep 1
    done

    if [[ "$port_ready" -ne 1 ]]; then
        die "پس از 30 ثانیه هیچ سرویس TCP/UDP روی پورت مورد انتظار ${port} در حال شنود نیست."
    fi
done

echo "✅ پورت Backend (8000) در حال شنود است؛ سرویس GPS دیگر listener مستقیم TCP/UDP ندارد."
echo "✅ دیتابیس، سوپریوزر و سرویس‌ها بررسی شدند."
echo "✅ تنظیم مجوز tcpdump و sudoers دست‌نخورده باقی مانده است."
echo "وضعیت Backend: sudo systemctl status sana-backend.service --no-pager"
echo "وضعیت GPS: sudo systemctl status sana-gps.service --no-pager"

BACKEND_STOPPED=0
SERVICE_STOPPED=0
RUN_SUCCEEDED=1

echo
echo "============================================================"
echo "✅ بازسازی دیتابیس و راه‌اندازی سرویس‌ها با موفقیت انجام شدند."
echo "Backend و GPS فعال هستند؛ پنل Vite که جداگانه اجرا می‌شود در این اسکریپت مدیریت نمی‌شود."
echo "مدت اجرا: $(( $(date +%s) - START_TIME )) ثانیه"
echo "گزارش کامل: $LOG_FILE"
echo "============================================================"
