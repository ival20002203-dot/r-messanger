#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
expected_version="13.8.3"
actual_version="$(tr -d '[:space:]' < VERSION)"
[ "$actual_version" = "$expected_version" ] || { echo "ERROR: expected R-Mes $expected_version, found $actual_version" >&2; exit 1; }
[ -f .env ] || { echo "ERROR: .env is missing. Restore the production .env before deployment." >&2; exit 1; }

mkdir -p client_updates/windows client_updates/android media private_media logs backups
chmod +x scripts/*.sh
docker compose config --quiet
docker compose up -d --build
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py shell -c 'from django.conf import settings; from django.utils import timezone; print({"timezone":settings.TIME_ZONE,"server_time":timezone.localtime().isoformat()})'
curl -fsS http://127.0.0.1:8000/healthz/ >/dev/null
docker compose ps -a
echo "READY: R-Mes $actual_version"
