#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then echo "ERROR: .env not found in $(pwd)" >&2; exit 1; fi
if grep -q '^WEB_ACCESS_ENABLED=' .env; then
  sed -i 's/^WEB_ACCESS_ENABLED=.*/WEB_ACCESS_ENABLED=0/' .env
else
  printf '\nWEB_ACCESS_ENABLED=0\n' >> .env
fi
docker compose up -d --force-recreate web
printf '\nWeb UI: OFF\nDesktop: ON\n'
