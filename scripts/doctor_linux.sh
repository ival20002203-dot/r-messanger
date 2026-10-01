#!/bin/sh
set -eu
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
echo "=== Localgram v7 production doctor ==="
$COMPOSE ps
$COMPOSE exec web1 python manage.py check
for app in accounts chat moderation securitycenter operations; do $COMPOSE exec web1 python manage.py showmigrations "$app"; done
$COMPOSE exec web1 python manage.py shell -c "from django.db import connection; from django.core.cache import cache; c=connection.cursor(); c.execute('select 1'); print({'db':c.fetchone()[0],'redis':cache.get_or_set('doctor','ok',30)})"
$COMPOSE exec web1 python manage.py shell -c "import clamd; from django.conf import settings; c=clamd.ClamdNetworkSocket(settings.CLAMAV_HOST,settings.CLAMAV_PORT,timeout=8); print(c.ping(),c.version())"
$COMPOSE exec web1 python manage.py shell -c "from django.core.cache import cache; print({'moderator':bool(cache.get('localgram:moderation_worker:alive')),'security':bool(cache.get('localgram:security_worker:alive')),'scheduler':bool(cache.get('localgram:scheduler_worker:alive'))})"
$COMPOSE exec web1 python manage.py shell -c "from apps.accounts.models import RoleProfile,DeviceSession; from apps.chat.models import Poll,ScheduledPost; from apps.operations.models import BackupVerification,RateLimitEvent; print({'roles':RoleProfile.objects.count(),'suspicious_devices':DeviceSession.objects.filter(trust_status__in=['suspicious','blocked'],revoked_at__isnull=True).count(),'polls':Poll.objects.count(),'scheduled':ScheduledPost.objects.filter(status='scheduled').count(),'restore_checks':BackupVerification.objects.count(),'rate_events':RateLimitEvent.objects.count()})"
$COMPOSE logs --tail=40 nginx web1 web2 moderator securityworker scheduler
echo "=== Localgram v7 production doctor OK ==="
