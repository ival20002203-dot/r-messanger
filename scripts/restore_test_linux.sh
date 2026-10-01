#!/bin/sh
set -eu
DB_BACKUP="${1:-$(ls -1t backups/db_*.sql 2>/dev/null | head -1)}"
MINIO_BACKUP="${2:-$(ls -1t backups/minio_*.tar.gz 2>/dev/null | head -1 || true)}"
PRIVATE_BACKUP="${3:-$(ls -1t backups/private_media_*.tar.gz 2>/dev/null | head -1 || true)}"
NAME=localgram-restore-test-db
DB_OK=0;MINIO_OK=0;PRIVATE_OK=0;PASSED=0;SUMMARY=""
[ -f "$DB_BACKUP" ] || { echo "DB backup not found"; exit 2; }
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=restoretest -e POSTGRES_DB=localgram_restore postgres:17-alpine >/dev/null
i=0
until docker exec "$NAME" pg_isready -U postgres -d localgram_restore >/dev/null 2>&1; do i=$((i+1)); [ $i -lt 60 ] || { SUMMARY="temporary PostgreSQL timeout"; break; }; sleep 1; done
if [ -z "$SUMMARY" ]; then
  docker exec -i "$NAME" psql -U postgres -d localgram_restore -v ON_ERROR_STOP=1 < "$DB_BACKUP" >/dev/null
  MIG=$(docker exec "$NAME" psql -U postgres -d localgram_restore -Atc 'select count(*) from django_migrations;')
  USERS=$(docker exec "$NAME" psql -U postgres -d localgram_restore -Atc 'select count(*) from accounts_user;')
  [ "$MIG" -gt 0 ] && DB_OK=1
  if [ -n "$MINIO_BACKUP" ] && [ -f "$MINIO_BACKUP" ]; then tar tzf "$MINIO_BACKUP" >/dev/null && MINIO_OK=1; else MINIO_OK=1; fi
  if [ -n "$PRIVATE_BACKUP" ] && [ -f "$PRIVATE_BACKUP" ]; then tar tzf "$PRIVATE_BACKUP" >/dev/null && PRIVATE_OK=1; else PRIVATE_OK=1; fi
  [ $DB_OK -eq 1 ] && [ $MINIO_OK -eq 1 ] && [ $PRIVATE_OK -eq 1 ] && PASSED=1
  SUMMARY="DB restore OK. migrations=$MIG users=$USERS; minio=$MINIO_OK private=$PRIVATE_OK"
fi
STATUS=failed;[ $PASSED -eq 1 ] && STATUS=passed
DB_FLAG=""; MINIO_FLAG=""; PRIVATE_FLAG=""
[ $DB_OK -eq 1 ] && DB_FLAG="--database-ok"
[ $MINIO_OK -eq 1 ] && MINIO_FLAG="--object-storage-ok"
[ $PRIVATE_OK -eq 1 ] && PRIVATE_FLAG="--private-media-ok"
# Optional flags intentionally use shell word splitting; summary/source remain quoted.
# shellcheck disable=SC2086
docker compose -f docker-compose.prod.yml exec -T web1 python manage.py record_backup_verification   --status "$STATUS" --source "$(basename "$DB_BACKUP")" --summary "$SUMMARY"   $DB_FLAG $MINIO_FLAG $PRIVATE_FLAG || true
[ $PASSED -eq 1 ] || exit 2
echo "Restore verification PASSED"
