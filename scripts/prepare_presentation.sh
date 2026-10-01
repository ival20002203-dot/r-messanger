#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=".env"
[ -f "$ENV_FILE" ] || { echo "ERROR: $ENV_FILE not found"; exit 1; }

set_env(){
  local key="$1" value="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
SERVER_IP="${SERVER_IP:-10.10.10.130}"

# Enable the features that early test .env files intentionally disabled.
set_env CONTENT_MODERATION_ENABLED 1
set_env CONTENT_MODERATION_TEXT_ENABLED 1
set_env CONTENT_MODERATION_MEDIA_ENABLED 1
set_env CONTENT_MODERATION_OCR_ENABLED 1
set_env TURN_ENABLED 1
set_env TURN_HOST "$SERVER_IP"
set_env RTC_ICE_SERVERS_JSON '[]'

if ! grep -q '^TURN_USERNAME=' "$ENV_FILE"; then set_env TURN_USERNAME rmes; fi
if ! grep -q '^TURN_PASSWORD=' "$ENV_FILE"; then
  if command -v openssl >/dev/null 2>&1; then TURN_PASS="$(openssl rand -hex 18)"; else TURN_PASS="RMes-$(date +%s)-Turn"; fi
  set_env TURN_PASSWORD "$TURN_PASS"
  echo "TURN_PASSWORD generated and saved in .env (not printed)."
fi

chmod 600 "$ENV_FILE" || true

echo "== Building/recreating R-Mes 13.4 presentation services =="
docker compose config --quiet
docker compose up -d --build --force-recreate web moderator securityworker coturn scheduler

echo "== Database migrations =="
docker compose exec -T web python manage.py migrate --noinput

echo "== Repairing old pending/error queues =="
docker compose exec -T web python manage.py repair_presentation_state

echo "== Django system check =="
docker compose exec -T web python manage.py check

echo "== Services =="
docker compose ps

echo
echo "Presentation mode ready. TURN host: $SERVER_IP"
echo "If UFW is active, run: bash scripts/enable_call_ports.sh"
