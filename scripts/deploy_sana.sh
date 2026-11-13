#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/opt/sana"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT_LINK="$APP_ROOT/current"
BACKEND_ENV="/etc/sana-backend.env"
DOMAIN="sana.etminan.net"
SERVICE="sana-backend-production.service"
DEPLOY_USER="$(id -un)"

SWITCHED=0
RELEASE_CREATED=0
RELEASE_DIR=""
PREVIOUS_TARGET=""

fail() {
    echo
    echo "ERROR: $*" >&2
    exit 1
}

rollback() {
    local rc=$?
    if [[ "$rc" -ne 0 ]]; then
        if [[ "$SWITCHED" -eq 1 ]]; then
            echo
            echo "Deployment failed. Restoring previous release..."

            if [[ -n "$PREVIOUS_TARGET" && -d "$PREVIOUS_TARGET" ]]; then
                sudo rm -f "$APP_ROOT/current.rollback"
                sudo ln -s "$PREVIOUS_TARGET" "$APP_ROOT/current.rollback"
                sudo mv -Tf "$APP_ROOT/current.rollback" "$CURRENT_LINK"
                sudo systemctl restart "$SERVICE" || true
                echo "Previous release restored: $PREVIOUS_TARGET"

                if [[ -n "$RELEASE_DIR" && -d "$RELEASE_DIR" ]]; then
                    sudo rm -rf -- "$RELEASE_DIR"
                    echo "Failed release removed."
                fi
            else
                echo "WARNING: Previous release target is unavailable."
            fi
        elif [[ "$RELEASE_CREATED" -eq 1 && -n "$RELEASE_DIR" && -d "$RELEASE_DIR" ]]; then
            echo "Removing incomplete release..."
            sudo rm -rf -- "$RELEASE_DIR"
        fi
    fi
}
trap rollback EXIT

[[ "$DEPLOY_USER" != "root" ]] || fail "Run this script as the deploy user, not root."

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

[[ "$(git branch --show-current)" == "main" ]] || fail "Current branch must be main."
[[ -z "$(git status --porcelain)" ]] || fail "Git working tree is not clean. Commit or stash changes first."
git remote get-url origin | grep -q 'IrajAzarvand/SANA' || fail "Unexpected Git remote."

[[ -f "$BACKEND_ENV" ]] || fail "Production backend environment file is missing."
[[ -f "sana-backend/requirements-production.lock" ]] || fail "Production requirements lock is missing."
[[ -f "sana-panel/package-lock.json" ]] || fail "Frontend package-lock.json is missing."
[[ -f "sana-panel/.env" ]] || fail "Frontend .env is missing on the server."
[[ -f "sana-panel/.env.production" ]] || fail "Frontend .env.production is missing on the server."

grep -qx 'VITE_API_URL=/api' "sana-panel/.env.production" || fail "Production frontend API URL must be /api."

echo "Fetching latest main..."
git fetch origin main
git merge --ff-only origin/main

[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] ||
    fail "Local main is not equal to origin/main. Push your changes first."

COMMIT="$(git rev-parse HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
RELEASE_ID="$(date +%Y%m%d-%H%M%S)-$SHORT_SHA"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_ID"

echo "Preparing release: $RELEASE_ID"

sudo mkdir -p "$RELEASES_DIR"
sudo mkdir "$RELEASE_DIR"
RELEASE_CREATED=1
sudo chown "$DEPLOY_USER:$DEPLOY_USER" "$RELEASE_DIR"

PREVIOUS_TARGET="$(readlink -f "$CURRENT_LINK" || true)"
[[ -n "$PREVIOUS_TARGET" && -d "$PREVIOUS_TARGET" ]] ||
    fail "Current production release is missing; refusing deployment."

echo "Extracting source..."
git archive "$COMMIT" | tar -x -C "$RELEASE_DIR"

BACKEND_DIR="$RELEASE_DIR/sana-backend"
FRONTEND_DIR="$RELEASE_DIR/sana-panel"

[[ -d "$BACKEND_DIR" && -d "$FRONTEND_DIR" ]] || fail "Expected backend or frontend source directory is missing."

echo "Preparing frontend environment..."
cp "$REPO_ROOT/sana-panel/.env" "$FRONTEND_DIR/.env"
cp "$REPO_ROOT/sana-panel/.env.production" "$FRONTEND_DIR/.env.production"

echo "Installing frontend dependencies..."
(
    cd "$FRONTEND_DIR"
    npm ci
    VITE_API_URL=/api npm run build
)

[[ -d "$FRONTEND_DIR/dist" ]] || fail "Frontend build did not produce dist."

mkdir -p "$RELEASE_DIR/frontend"
mv "$FRONTEND_DIR/dist" "$RELEASE_DIR/frontend/dist"
rm -rf "$FRONTEND_DIR"

echo "Preparing backend..."
mv "$BACKEND_DIR" "$RELEASE_DIR/backend"
BACKEND_DIR="$RELEASE_DIR/backend"

python3.12 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --index-url https://package-mirror.liara.ir/repository/pypi/simple/ --no-cache-dir -r "$BACKEND_DIR/requirements-production.lock"

[[ -d "$APP_ROOT/shared/media" ]] || fail "Shared media directory is missing."
ln -s "$APP_ROOT/shared/media" "$BACKEND_DIR/media"

run_django() {
    sudo systemd-run \
        --quiet --wait --pipe --collect \
        --uid="$DEPLOY_USER" \
        --working-directory="$BACKEND_DIR" \
        --property="EnvironmentFile=$BACKEND_ENV" \
        "$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/manage.py" "$@"
}

echo "Checking Django configuration..."
run_django check

echo "Applying database migrations..."
run_django migrate --noinput

echo "Collecting static files..."
run_django collectstatic --noinput

echo "Activating release..."
sudo rm -f "$APP_ROOT/current.next"
sudo ln -s "$RELEASE_DIR" "$APP_ROOT/current.next"
sudo mv -Tf "$APP_ROOT/current.next" "$CURRENT_LINK"
SWITCHED=1

echo "Restarting production backend..."
sudo systemctl restart "$SERVICE"
sudo systemctl is-active --quiet "$SERVICE" || fail "Production backend service is not active."

echo "Checking backend..."
curl --fail --silent --show-error --max-time 15 \
    -H "Host: $DOMAIN" \
    -H "X-Forwarded-Proto: https" \
    "http://127.0.0.1:8001/admin/login/" \
    -o /dev/null || fail "Backend health check failed."

echo "Checking frontend through local HTTPS..."
curl --insecure --fail --silent --show-error --max-time 15 \
    --resolve "$DOMAIN:443:127.0.0.1" \
    "https://$DOMAIN/" \
    -o /dev/null || fail "Frontend health check failed."

SWITCHED=0

echo "Deployment successful."

echo "Pruning old releases (keeping three)..."
mapfile -t RELEASE_NAMES < <(
    sudo find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d \
        -printf '%f\n' | sort -r
)

COUNT=0
CURRENT_NAME="$(basename "$(readlink -f "$CURRENT_LINK")")"
PREVIOUS_NAME="$(basename "$PREVIOUS_TARGET")"

for NAME in "${RELEASE_NAMES[@]}"; do
    if [[ "$NAME" == "$CURRENT_NAME" || "$NAME" == "$PREVIOUS_NAME" ]]; then
        COUNT=$((COUNT + 1))
        continue
    fi

    if [[ "$COUNT" -lt 3 ]]; then
        COUNT=$((COUNT + 1))
        continue
    fi

    TARGET="$RELEASES_DIR/$NAME"
    case "$TARGET" in
        "$RELEASES_DIR"/20*) sudo rm -rf -- "$TARGET" || echo "WARNING: Could not remove $TARGET" ;;
        *) echo "WARNING: Skipping unexpected release path: $TARGET" ;;
    esac
done

echo
echo "Release: $RELEASE_ID"
echo "Commit:  $COMMIT"
echo "Current: $(readlink -f "$CURRENT_LINK")"
