#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$REPO_ROOT/scripts/sana-traccar-port-manager"
TARGET="/usr/local/sbin/sana-traccar-port-manager"
SUDOERS="/etc/sudoers.d/sana-traccar-port-manager"
DJANGO_USER="www-data"
if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo $0"; exit 1; fi
if [[ ! -f "$SOURCE" ]]; then echo "Missing helper: $SOURCE" >&2; exit 1; fi
if ! id "$DJANGO_USER" >/dev/null 2>&1; then echo "Django service user '$DJANGO_USER' does not exist; edit DJANGO_USER in this script." >&2; exit 1; fi
install -o root -g root -m 0750 "$SOURCE" "$TARGET"
install -d -o root -g root -m 0750 /var/backups/sana-traccar
printf '%s ALL=(root) NOPASSWD: %s\n' "$DJANGO_USER" "$TARGET" > "$SUDOERS"
chmod 0440 "$SUDOERS"
visudo -cf "$SUDOERS"
echo "Installed $TARGET and restricted sudoers rule for $DJANGO_USER."
echo "Review UFW policy and confirm the Traccar config path before using the admin UI."
