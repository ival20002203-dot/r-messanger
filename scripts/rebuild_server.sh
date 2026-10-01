#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p client_updates/windows client_updates/android media private_media logs backups

echo "[1/5] Validate compose"
docker compose config --quiet

echo "[2/5] Build and recreate R-Mes services"
docker compose up -d --build

echo "[3/5] Apply migrations"
docker compose exec -T web python manage.py migrate --noinput

echo "[4/5] Django check"
docker compose exec -T web python manage.py check

echo "[5/5] Containers"
docker compose ps

echo "R-Mes server update complete. Persistent Docker volumes were not removed."
