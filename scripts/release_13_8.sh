#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
expected_version="13.8.0"
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
echo "[1/7] Проверка Docker Compose"
docker compose config --quiet
echo "[2/7] Сборка и запуск сервисов"
docker compose up -d --build
echo "[3/7] Миграции базы данных"
docker compose exec -T web python manage.py migrate --noinput
echo "[4/7] Восстановление фоновых очередей"
docker compose exec -T web python manage.py repair_presentation_state || true
echo "[5/7] Проверка Django"
docker compose exec -T web python manage.py check
echo "[6/7] Проверка готовности"
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
echo "[7/7] Состояние контейнеров"
docker compose ps -a
echo "READY: R-Mes $actual_version"
