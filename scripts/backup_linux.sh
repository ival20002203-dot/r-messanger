#!/bin/sh
set -eu
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p backups
POSTGRES_USER="${POSTGRES_USER:-localgram}"
POSTGRES_DB="${POSTGRES_DB:-localgram}"
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "backups/db_${STAMP}.sql"
docker run --rm -v localgram_localgram_minio:/data:ro -v "$(pwd)/backups:/backup" alpine:3.20 sh -c "cd /data && tar czf /backup/minio_${STAMP}.tar.gz ."
docker run --rm -v localgram_localgram_private_media:/data:ro -v "$(pwd)/backups:/backup" alpine:3.20 sh -c "cd /data && tar czf /backup/private_media_${STAMP}.tar.gz ."
echo "Backup completed: backups/*_${STAMP}*"
# Keep local test backups bounded on small/free VPS disks.
find backups -type f -mtime +14 -delete 2>/dev/null || true
