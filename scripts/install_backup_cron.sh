#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/logs" "$ROOT/backups"
cat >/etc/cron.d/rmes-backup <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
17 3 * * * root cd "$ROOT" && ./scripts/backup_linux.sh >> "$ROOT/logs/backup.log" 2>&1
47 4 * * 0 root cd "$ROOT" && ./scripts/restore_test_linux.sh >> "$ROOT/logs/restore-test.log" 2>&1
CRON
chmod 0644 /etc/cron.d/rmes-backup
echo "R-Mes backup cron installed: daily backup 03:17, weekly restore test Sunday 04:47."
