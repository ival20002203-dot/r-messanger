#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== R-Mes presentation check =="
printf 'Version: '; cat VERSION; echo

docker compose config --quiet
docker compose ps

echo "-- Django check --"
docker compose exec -T web python manage.py check

echo "-- Migrations --"
docker compose exec -T web python manage.py showmigrations chat | tail -n 12
docker compose exec -T web python manage.py showmigrations operations | tail -n 12

echo "-- Feature flags --"
docker compose exec -T web python manage.py shell -c 'from django.conf import settings; print("moderation:",settings.CONTENT_MODERATION_ENABLED,settings.CONTENT_MODERATION_MEDIA_ENABLED,settings.CONTENT_MODERATION_OCR_ENABLED); print("ICE:",settings.RTC_ICE_SERVERS)'

echo "-- Worker health/cache --"
docker compose exec -T web python manage.py shell -c 'from django.core.cache import cache; print("moderator:",cache.get("localgram:moderation_worker:alive")); print("security:",cache.get("localgram:security_worker:alive"))'

echo "-- Queue summary --"
docker compose exec -T web python manage.py shell -c 'from apps.securitycenter.models import AttachmentScanJob as S; from apps.moderation.models import ModerationScanJob as M,ModerationCase as C; print("security",dict((x,S.objects.filter(status=x).count()) for x in ["queued","processing","done","error"])); print("moderation",dict((x,M.objects.filter(status=x).count()) for x in ["queued","processing","done","error"])); print("moderation_cases",C.objects.count())'

echo "-- Health --"
curl -fsS http://127.0.0.1:8000/healthz/ || true; echo

echo "-- TURN --"
if docker compose ps --status running --services | grep -qx coturn; then echo "coturn: running"; else echo "coturn: NOT RUNNING"; exit 2; fi

echo "Presentation prerequisites look OK."
