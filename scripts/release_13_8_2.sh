#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
expected_version="13.8.2"
actual_version="$(tr -d '[:space:]' < VERSION)"

if [ "$actual_version" != "$expected_version" ]; then
  echo "ERROR: expected R-Mes $expected_version, found $actual_version" >&2
  exit 1
fi
if [ ! -f .env ]; then
  echo "ERROR: .env is missing. Restore the production .env before deployment." >&2
  exit 1
fi

mkdir -p client_updates/windows client_updates/android media private_media logs backups
chmod +x scripts/*.sh
echo "[1/8] Проверка Docker Compose"
docker compose config --quiet
echo "[2/8] Сборка и запуск сервисов"
docker compose up -d --build
echo "[3/8] Миграции базы данных"
docker compose exec -T web python manage.py migrate --noinput
echo "[4/8] Восстановление фоновых очередей"
docker compose exec -T web python manage.py repair_presentation_state || true
echo "[5/8] Проверка Django"
docker compose exec -T web python manage.py check
echo "[6/8] Проверка времени и присутствия"
docker compose exec -T web python manage.py shell -c 'from django.conf import settings; from django.utils import timezone; print({"timezone":settings.TIME_ZONE,"server_time":timezone.localtime().isoformat()})'
echo "[7/8] Проверка готовности"
health_ok=0
for attempt in 1 2 3 4 5 6; do
  if curl -fsS http://127.0.0.1:8000/healthz/ >/dev/null; then health_ok=1;break;fi
  sleep 2
done
if [ "$health_ok" -ne 1 ]; then
  echo "ERROR: R-Mes health check failed." >&2
  docker compose ps -a
  exit 1
fi
echo "[8/8] Состояние контейнеров и очередей"
docker compose ps -a
docker compose exec -T web python manage.py localgram_status
echo "READY: R-Mes $actual_version"
