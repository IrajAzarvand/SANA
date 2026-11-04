#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$REPO_ROOT/scripts/sana-traccar-port-manager"
LIVE_CAPTURE_SOURCE="$REPO_ROOT/scripts/sana-traccar-live-capture"
TARGET="/usr/local/sbin/sana-traccar-port-manager"
LIVE_CAPTURE_TARGET="/usr/local/sbin/sana-traccar-live-capture"
SUDOERS="/etc/sudoers.d/sana-traccar-port-manager"
# This SANA server runs Django as iraj (see sana-backend.service).
# Change this value if the service account differs on another deployment.
DJANGO_USER="iraj"
if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo $0"; exit 1; fi
if [[ ! -f "$SOURCE" ]]; then echo "Missing helper: $SOURCE" >&2; exit 1; fi
if [[ ! -f "$LIVE_CAPTURE_SOURCE" ]]; then echo "Missing helper: $LIVE_CAPTURE_SOURCE" >&2; exit 1; fi
if ! id "$DJANGO_USER" >/dev/null 2>&1; then echo "Django service user '$DJANGO_USER' does not exist; edit DJANGO_USER in this script." >&2; exit 1; fi
install -o root -g root -m 0750 "$SOURCE" "$TARGET"
install -o root -g root -m 0750 "$LIVE_CAPTURE_SOURCE" "$LIVE_CAPTURE_TARGET"
install -d -o root -g root -m 0750 /var/backups/sana-traccar
cat > "$SUDOERS" <<EOF
$DJANGO_USER ALL=(root) NOPASSWD: $TARGET
$DJANGO_USER ALL=(root) NOPASSWD: $LIVE_CAPTURE_TARGET
EOF
chmod 0440 "$SUDOERS"
visudo -cf "$SUDOERS"
echo "Installed $TARGET and $LIVE_CAPTURE_TARGET."
echo "Sudo is restricted to these root-owned helpers; the live capture helper accepts only a validated port and transport."
