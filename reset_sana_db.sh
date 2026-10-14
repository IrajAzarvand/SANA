#!/usr/bin/env bash
# SANA - بازسازی دیتابیس آزمایشی و راه‌اندازی GPS
# اجرا: bash ~/Desktop/SANA/reset_sana_db.sh
#
# هشدار: دیتابیس sana_db کاملاً حذف و دوباره ساخته می‌شود.
# همه داده‌ها، کاربران و سوپریوزر قبلی آن از بین می‌روند.

set -Eeuo pipefail
IFS=$'\n\t'

ROOT="${SANA_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
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
START_TIME="$(date +%s)"

exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
    rc=$?
    echo
    echo "❌ خطا در مرحله: $STEP"
    echo "کد خروج: $rc"
    echo "گزارش کامل: $LOG_FILE"

    if [[ "$SERVICE_STOPPED" == "1" ]]; then
        sudo systemctl stop sana-gps >/dev/null 2>&1 || true
        echo "سرویس GPS متوقف نگه داشته شد."
    fi

    exit "$rc"
}
trap on_error ERR

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

echo "SANA - Database Reset and GPS Bootstrap"
echo "زمان: $(date --iso-8601=seconds)"
echo "ریشه پروژه: $ROOT"
echo "دیتابیس: $DB_NAME"
echo "مالک دیتابیس: $DB_OWNER"
echo "گزارش اجرا: $LOG_FILE"

# بررسی اولیه مسیرها و فایل‌های لازم
[[ -d "$BACKEND" ]] || die "پوشه sana-backend پیدا نشد."
[[ -d "$GPS" ]] || die "پوشه sana-gps پیدا نشد."
[[ -f "$MANAGE" ]] || die "فایل manage.py پیدا نشد."
[[ -x "$PYTHON" ]] || die "Python محیط مجازی پیدا نشد."
[[ -d "$SQL_DIR" ]] || die "پوشه sql پیدا نشد."

command -v sudo >/dev/null || die "sudo نصب نیست."
command -v psql >/dev/null || die "psql پیدا نشد."
command -v systemctl >/dev/null || die "systemctl پیدا نشد."

# اسکریپت‌های SQL لازم برای این نسخه
SQL_FILES=(
    "0000_roles.sql"
    "0001_gps_schema.sql"
    "0002_detected_protocol_registration.sql"
    "0003_purge_device_telemetry.sql"
    "0005_grant_sana_user_gps_permissions.sql"
)

for file in "${SQL_FILES[@]}"; do
    [[ -f "$SQL_DIR/$file" ]] ||
        die "فایل SQL لازم پیدا نشد: $SQL_DIR/$file"
done

echo
echo "⚠️ هشدار: این عملیات دیتابیس '$DB_NAME' را کامل حذف می‌کند."
echo "تمام کاربران، داده‌های GPS و اطلاعات داخل آن پاک خواهند شد."
echo "جدول fleet_gpstelemetry نیز همراه دیتابیس حذف و با migrationها بازسازی می‌شود."
echo "این اسکریپت به‌صورت مستقل دستور حذف جدول fleet_gpstelemetry اجرا نمی‌کند."
echo

read -r -p "برای تأیید، نام دیتابیس را دقیقاً وارد کن [$DB_NAME]: " CONFIRM
[[ "$CONFIRM" == "$DB_NAME" ]] ||
    die "تأیید صحیح نبود؛ دیتابیس حذف نشد."

# ۱. توقف سرویس GPS
step "۱/۱۰ - توقف سرویس GPS"

sudo systemctl stop sana-gps
SERVICE_STOPPED=1

if systemctl is-active --quiet sana-gps; then
    die "سرویس GPS هنوز فعال است."
fi

echo "✅ سرویس GPS متوقف است."

# ۲. بررسی نقش PostgreSQL
step "۲/۱۰ - بررسی نقش PostgreSQL"

ROLE_EXISTS="$(
    sudo -u postgres psql -X -d postgres -At \
        -v role_name="$DB_OWNER" \
        -c "SELECT count(*) FROM pg_roles WHERE rolname = :'role_name'"
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

    sudo -u postgres psql -X -v ON_ERROR_STOP=1 \
        -d "$DB_NAME" \
        -f "$SQL_DIR/$file"
done

echo "✅ SQLهای GPS اجرا شدند."

# ۸. آزمون اتصال، وجود جداول و دسترسی به جداول مشترک
step "۸/۱۰ - آزمون دیتابیس و جداول"

cd "$BACKEND"

EXPECTED_DB="$DB_NAME" EXPECTED_USER="$DB_OWNER" \
"$PYTHON" "$MANAGE" shell -c '
import os
from django.db import connection

expected_db = os.environ["EXPECTED_DB"]
expected_user = os.environ["EXPECTED_USER"]

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT
            current_database(),
            current_user,
            to_regclass(%s),
            to_regclass(%s),
            to_regclass(%s),
            to_regclass(%s),
            to_regclass(%s)
    """, [
        "public.fleet_gpstelemetry",
        "public.fleet_gt06position",
        "gps.raw_packet",
        "gps.location_history",
        "gps.current_state",
    ])

    db, user, telemetry, legacy_gt06, raw, history, state = cursor.fetchone()

    print("Database:", db)
    print("Database user:", user)
    print("fleet_gpstelemetry:", telemetry)
    print("legacy fleet_gt06position:", legacy_gt06)
    print("gps.raw_packet:", raw)
    print("gps.location_history:", history)
    print("gps.current_state:", state)

    assert db == expected_db, f"Wrong database: {db}"
    assert user == expected_user, f"Wrong database user: {user}"
    assert telemetry is not None, "fleet_gpstelemetry is missing"
    assert legacy_gt06 is None, "Legacy fleet_gt06position unexpectedly exists"
    assert raw is not None, "gps.raw_packet is missing"
    assert history is not None, "gps.location_history is missing"
    assert state is not None, "gps.current_state is missing"

    # آزمون واقعی SELECT با کاربر برنامه
    for table in (
        "gps.raw_packet",
        "gps.location_history",
        "gps.current_state",
    ):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"SELECT access OK: {table}; rows={cursor.fetchone()[0]}")

    cursor.execute("SELECT postgis_full_version()")
    print("PostGIS:", cursor.fetchone()[0])

print("✅ Database checks passed.")
'

echo "✅ جداول و دسترسی‌های اصلی تأیید شدند."

# ۹. ساخت سوپریوزر
step "۹/۱۰ - ساخت سوپریوزر سایت"

echo "نام کاربری، ایمیل و رمز را در پرسش‌های Django وارد کن."
echo "رمز در فایل اسکریپت یا گزارش ذخیره نمی‌شود."

"$PYTHON" "$MANAGE" createsuperuser

echo "✅ مرحله ساخت سوپریوزر پایان یافت."

# ۱۰. راه‌اندازی سرویس و بررسی پورت‌ها
step "۱۰/۱۰ - راه‌اندازی و آزمون سرویس GPS"

sudo systemctl start sana-gps
sleep 2

if ! systemctl is-active --quiet sana-gps; then
    die "سرویس GPS فعال نشد."
fi

sudo systemctl status sana-gps --no-pager

echo
echo "آخرین لاگ‌های GPS:"
sudo journalctl -u sana-gps -n 30 --no-pager

echo
echo "پورت‌های GPS:"
sudo ss -lntup | grep -E ':9000|:9001' ||
    die "پورت 9000 یا 9001 در وضعیت انتظار نیست."

SERVICE_STOPPED=0

echo
echo "============================================================"
echo "✅ تمام مراحل با موفقیت انجام شدند."
echo "مدت اجرا: $(( $(date +%s) - START_TIME )) ثانیه"
echo "گزارش کامل: $LOG_FILE"
echo "============================================================"
