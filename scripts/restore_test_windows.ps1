param(
  [string]$DbBackup = "",
  [string]$MinioBackup = "",
  [string]$PrivateBackup = ""
)
$ErrorActionPreference = "Stop"
$project = (Get-Location).Path
$container = "localgram-restore-test-db"
$passed = $false
$dbOk = $false
$minioOk = $false
$privateOk = $false
$summary = ""

if (-not $DbBackup) {
  $DbBackup = (Get-ChildItem ".\backups\db_*.sql" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}
if (-not $MinioBackup) {
  $MinioBackup = (Get-ChildItem ".\backups\minio_*.tar.gz" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}
if (-not $PrivateBackup) {
  $PrivateBackup = (Get-ChildItem ".\backups\private_media_*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}
if (-not $DbBackup -or -not (Test-Path $DbBackup)) { throw "DB backup not found" }

try {
  docker rm -f $container 2>$null | Out-Null
  docker run -d --name $container -e POSTGRES_PASSWORD=restoretest -e POSTGRES_DB=localgram_restore postgres:17-alpine | Out-Null
  for ($i=0;$i -lt 60;$i++) {
    docker exec $container pg_isready -U postgres -d localgram_restore *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
  }
  if ($LASTEXITCODE -ne 0) { throw "Temporary PostgreSQL did not become ready" }
  cmd /c "docker exec -i $container psql -U postgres -d localgram_restore -v ON_ERROR_STOP=1 < `"$DbBackup`"" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "SQL restore failed" }
  $mig = docker exec $container psql -U postgres -d localgram_restore -Atc "select count(*) from django_migrations;"
  $users = docker exec $container psql -U postgres -d localgram_restore -Atc "select count(*) from accounts_user;"
  if ([int]$mig -lt 1) { throw "django_migrations is empty" }
  $dbOk=$true

  if ($MinioBackup -and (Test-Path $MinioBackup)) {
    $dir=Split-Path $MinioBackup -Parent;$name=Split-Path $MinioBackup -Leaf
    docker run --rm -v "${dir}:/backup:ro" alpine:3.20 sh -c "tar tzf /backup/$name >/dev/null"
    $minioOk=($LASTEXITCODE -eq 0)
  }
  if ($PrivateBackup -and (Test-Path $PrivateBackup)) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z=[IO.Compression.ZipFile]::OpenRead($PrivateBackup);$count=$z.Entries.Count;$z.Dispose();$privateOk=($count -ge 0)
  }
  $passed=$dbOk -and ($minioOk -or -not $MinioBackup) -and ($privateOk -or -not $PrivateBackup)
  $summary="DB restore OK. migrations=$mig users=$users; minio=$minioOk private=$privateOk"
} catch {
  $summary=$_.Exception.Message
  Write-Host $summary -ForegroundColor Red
} finally {
  docker rm -f $container 2>$null | Out-Null
  $status=if($passed){"passed"}else{"failed"}
  $args=@("compose","exec","web","python","manage.py","record_backup_verification","--status",$status,"--source",(Split-Path $DbBackup -Leaf),"--summary",$summary)
  if($dbOk){$args+="--database-ok"};if($minioOk){$args+="--object-storage-ok"};if($privateOk){$args+="--private-media-ok"}
  & docker @args
}
if(-not $passed){exit 2}
Write-Host "Restore verification PASSED" -ForegroundColor Green
