#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== R-Mes 13.6 presentation release =="
chmod +x scripts/*.sh || true
# Preserve explicit SMTP/server secrets; only ensure presentation features are enabled.
setenv(){ local k="$1" v="$2"; if grep -q "^${k}=" .env; then sed -i "s|^${k}=.*|${k}=${v}|" .env; else printf '%s=%s\n' "$k" "$v" >> .env; fi; }
setenv CONTENT_MODERATION_ENABLED 1
setenv CONTENT_MODERATION_MEDIA_ENABLED 1
setenv CONTENT_MODERATION_TEXT_ENABLED 1
setenv CONTENT_MODERATION_OCR_ENABLED 1
setenv TURN_ENABLED 1
docker compose config --quiet
docker compose up -d --build --force-recreate web securityworker moderator scheduler coturn
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py repair_presentation_state || true
docker compose exec -T web python manage.py check
docker compose ps -a
echo "== READY: $(cat VERSION) =="
