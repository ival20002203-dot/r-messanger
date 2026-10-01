#!/usr/bin/env bash
set -euo pipefail
cd "${1:-/opt/r-mes}"

echo "== R-Mes v12 upgrade =="
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Keep your existing server .env in this directory." >&2
  exit 1
fi

docker compose config --quiet
docker compose up -d --build

echo
echo "== Django check =="
docker compose exec -T web python manage.py check

echo
echo "== App-lock migration =="
docker compose exec -T web python manage.py showmigrations accounts | tail -12

echo
echo "== Containers =="
docker compose ps -a

echo
echo "R-Mes v12 server upgrade completed."
