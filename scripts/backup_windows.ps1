$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $PWD "backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "localgram" }
$dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "localgram" }

Write-Host "[1/4] PostgreSQL"
cmd /c "docker compose exec -T db pg_dump -U $dbUser $dbName > backups\db_$stamp.sql"

Write-Host "[2/4] Private moderation evidence"
if ((Test-Path ".\private_media") -and (Get-ChildItem ".\private_media" -Force -ErrorAction SilentlyContinue)) {
    Compress-Archive -Path ".\private_media\*" -DestinationPath ".\backups\private_media_$stamp.zip" -Force
}

Write-Host "[3/4] Legacy local media"
if ((Test-Path ".\media") -and (Get-ChildItem ".\media" -Force -ErrorAction SilentlyContinue)) {
    Compress-Archive -Path ".\media\*" -DestinationPath ".\backups\legacy_media_$stamp.zip" -Force
}

Write-Host "[4/4] MinIO object volume"
docker run --rm -v localgram_localgram_minio:/data:ro -v "${backupDir}:/backup" alpine:3.20 sh -c "cd /data && tar czf /backup/minio_$stamp.tar.gz ."

Write-Host "Backup completed: $backupDir" -ForegroundColor Green
