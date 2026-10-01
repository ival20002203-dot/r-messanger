param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "N:\VS CODE\localgram"
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot "_patch_backups\screen_privacy_rollback_$stamp"

$Files = @(
    "desktop\main.js",
    "desktop\preload.js",
    "static\app.js",
    "static\app.css",
    "templates\base.html",
    "mobile\android\app\src\main\java\uz\rmes\app\MainActivity.java",
    "mobile\ios\RMesIOS\SceneDelegate.swift"
)

if (!(Test-Path (Join-Path $ProjectRoot "manage.py"))) {
    throw "Не найден manage.py: $ProjectRoot"
}

Write-Host "[R-Messanger] Removing screenshot/screen-recording protection..." -ForegroundColor Cyan
Write-Host "Backup -> $BackupRoot" -ForegroundColor DarkGray

foreach ($rel in $Files) {
    $src = Join-Path $PatchRoot $rel
    $dst = Join-Path $ProjectRoot $rel
    if (!(Test-Path $src)) { throw "В rollback-патче отсутствует: $rel" }
    if (Test-Path $dst) {
        $bak = Join-Path $BackupRoot $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bak) | Out-Null
        Copy-Item -Force $dst $bak
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -Force $src $dst
    Write-Host "  OK $rel" -ForegroundColor DarkGray
}

Set-Location $ProjectRoot
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "manage.py check завершился с ошибкой" }
}

Write-Host "" 
Write-Host "Защита от скриншотов/записи экрана удалена." -ForegroundColor Green
Write-Host "Остальные изменения v15.1.2 не затронуты." -ForegroundColor Green
Write-Host "Backup: $BackupRoot"
