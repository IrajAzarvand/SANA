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

DB_NAME="${SANA_DB_NAME:-sana_db}"
DB_OWNER="${SANA_DB_OWNER:-sana_user}"

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

command -v sudo >/dev/null || die "sudo نصب نیست."
command -v psql >/dev/null || die "psql پیدا نشد."
command -v systemctl >/dev/null || die "systemctl پیدا نشد."

# SQLهای لازم برای schema فعلی GPS و اتصال Traccar.
# ترتیب اجرا مهم است: schema پایه، توابع/مجوزها، تطبیق نقشه، watcherها و سپس
# صف دستگاه‌های ناشناخته Traccar.
#
# عمداً 0004 و 0006 اجرا نمی‌شوند: این دو فایل نقش‌های سطح کلاستر PostgreSQL
# را پاک می‌کنند و بخشی از بازسازی یک دیتابیس نیستند.
# 0007 نیز بازنشسته و عملاً no-op است؛ 0008 وضعیت نهایی تطبیق نقشه را می‌سازد.
SQL_FILES=(
    "0000_roles.sql"
    "0001_gps_schema.sql"
    "0002_detected_protocol_registration.sql"
    "0003_purge_device_telemetry.sql"
    "0005_grant_sana_user_gps_permissions.sql"
    "0008_store_map_matches_in_existing_tables.sql"
    "0009_on_demand_map_matching.sql"
    "0010_traccar_integration.sql"
)

for file in "${SQL_FILES[@]}"; do
    [[ -f "$SQL_DIR/$file" ]] ||
        die "فایل SQL لازم پیدا نشد: $SQL_DIR/$file"
done

echo
echo "⚠️ هشدار: این عملیات دیتابیس '$DB_NAME' را کامل حذف می‌کند."
echo "تمام کاربران، داده‌های GPS و اطلاعات داخل آن پاک خواهند شد."
echo "تمام جدول‌های دیتابیس همراه خود دیتابیس حذف و بر اساس migrationهای فعلی و SQLهای GPS بازسازی می‌شوند."
echo "نکته معماری: کد فعلی هنوز برای نمایش نقشه/گزارش و دریافت موقعیت به جدول‌های GPS سانا وابسته است؛ این اسکریپت آن‌ها را فعلاً به‌عنوان لایه سازگاری بازسازی می‌کند. حذف ذخیره‌سازی تکراری باید پس از اصلاح و آزمون مسیر خواندن مستقیم از Traccar انجام شود."
echo "تنظیم مجوز پایش زنده شبکه در لینوکس مستقل است و در این عملیات دست‌کاری نمی‌شود."
echo

read -r -p "برای تأیید، نام دیتابیس را دقیقاً وارد کن [$DB_NAME]: " CONFIRM
[[ "$CONFIRM" == "$DB_NAME" ]] ||
    die "تأیید صحیح نبود؛ دیتابیس حذف نشد."

# بررسی اعتبار sudo پیش از توقف سرویس یا هر عملیات مخرب
step "آماده‌سازی دسترسی مدیریتی"
sudo -v

# ۱. توقف سرویس GPS و Backend برای جلوگیری از اتصال هنگام بازسازی دیتابیس
step "۱/۱۰ - توقف سرویس‌های GPS و Backend"

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
step "۲/۱۰ - بررسی نقش PostgreSQL"

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
step "۳/۱۰ - بازسازی دیتابیس"

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
step "۴/۱۰ - فعال‌سازی PostGIS"

sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
    -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "✅ PostGIS فعال است."

# ۵. اجرای تمام migrationهای Django
step "۵/۱۰ - اجرای migrationهای Django"

cd "$BACKEND"

# نام migrationها hard-code نشده است.
# Django تمام migrationهای ثبت‌شده و وابستگی‌هایشان را پیدا می‌کند.
"$PYTHON" "$MANAGE" migrate --noinput

echo "✅ اجرای migrationها کامل شد."

# ۶. بررسی Django و وضعیت migrationها
step "۶/۱۰ - آزمون تنظیمات Django"

"$PYTHON" "$MANAGE" check

"$PYTHON" "$MANAGE" makemigrations --check --dry-run

echo "✅ بررسی Django موفق بود."

# ۷. ساخت schema و تنظیمات GPS
step "۷/۱۰ - اجرای SQLهای GPS"

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
step "۸/۱۰ - آزمون دیتابیس و جداول"

cd "$BACKEND"

EXPECTED_DB="$DB_NAME" EXPECTED_USER="$DB_OWNER" \
"$PYTHON" "$MANAGE" shell -c '
import os
from django.db import connection
from django.db.migrations.loader import MigrationLoader

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

required_tables = [
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
    "gps.map_matching_watchers",
    "gps.traccar_unknown_device",
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

    # Validate columns that were added by the latest SQL schema changes, not just
    # table names. This catches a partially applied or outdated GPS schema.
    required_columns = {
        # Final Django schema after fleet migrations through 0012.
        "public.fleet_device": {
            "imei", "device_model_id", "protocol", "organization_id", "owner_user_id",
            "branch_id", "current_holder_organization_id", "current_holder_user_id",
            "vehicle_id", "management_status", "installed_at", "created_at", "updated_at",
        },
        "public.fleet_devicemodel": {
            "manufacturer", "name", "code", "protocol", "port", "traccar_version",
            "source_url", "is_verified", "created_at",
        },
        "public.fleet_gpstelemetry": {
            "device_id", "protocol", "gps_time", "latitude", "longitude",
            "gps_valid", "speed_kmh", "heading_deg", "altitude_m",
            "satellites", "attributes", "fingerprint", "raw_payload", "received_at",
        },
        "public.fleet_unknowngpsdata": {
            "session_id", "transport", "remote_address", "raw_payload",
            "identifier_candidate", "status", "received_at",
        },
        "gps.raw_packet": {
            "device_id", "protocol", "fingerprint", "received_at", "payload", "metadata",
        },
        "gps.location_history": {
            "device_id", "device_time", "server_received_at", "latitude", "longitude",
            "geom", "gps_valid", "matched_latitude", "matched_longitude",
            "matched_geom", "match_provider", "matched_at",
        },
        "gps.current_state": {
            "device_id", "device_time", "server_received_at", "last_seen",
            "latitude", "longitude", "geom", "gps_valid", "last_valid_latitude",
            "last_valid_longitude", "matched_latitude", "matched_longitude",
            "matched_geom", "match_provider", "matched_at",
        },
        "gps.map_matching_watchers": {
            "session_id", "user_id", "expires_at", "updated_at",
        },
        "gps.traccar_unknown_device": {
            "traccar_device_id", "unique_id", "name", "traccar_status",
            "first_seen_at", "last_seen_at", "last_synced_at", "review_status",
            "reviewed_at", "metadata",
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
        "gps.raw_packet",
        "gps.location_history",
        "gps.current_state",
        "gps.map_matching_watchers",
        "gps.traccar_unknown_device",
    ):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"SELECT access OK: {table}; rows={cursor.fetchone()[0]}")

    cursor.execute("SELECT postgis_full_version()")
    print("PostGIS:", cursor.fetchone()[0])

print("✅ Database, Django migrations, current GPS schema and privileges passed.")
'

echo "✅ جداول و دسترسی‌های اصلی تأیید شدند."

# ۹. ساخت سوپریوزر
step "۹/۱۰ - ساخت سوپریوزر سایت"

echo "نام کاربری، ایمیل و رمز را در پرسش‌های Django وارد کن."
echo "رمز در فایل اسکریپت یا گزارش ذخیره نمی‌شود."

"$PYTHON" "$MANAGE" createsuperuser

echo "✅ مرحله ساخت سوپریوزر پایان یافت."

# ۱۰. راه‌اندازی سرویس‌ها فقط پس از موفقیت آزمون دیتابیس و ساخت سوپریوزر
step "۱۰/۱۰ - راه‌اندازی و تأیید نهایی سرویس‌ها"

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
for port in 8000 9000 9001; do
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

echo "✅ پورت‌های 8000، 9000 و 9001 در حال شنود هستند."
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
