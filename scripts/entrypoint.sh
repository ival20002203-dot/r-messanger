#!/bin/sh
set -e
if [ "${SKIP_STARTUP_MIGRATIONS:-0}" != "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  python manage.py bootstrap_localgram
  python manage.py sync_client_versions || true
fi
exec "$@"
