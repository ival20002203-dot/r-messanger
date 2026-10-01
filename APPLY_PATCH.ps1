param(
    [Parameter(Mandatory=$false)]
    [string]$ProjectRoot = "N:\VS CODE\localgram"
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot "_patch_backups\v15_1_2_$stamp"

$Files = @(
    "VERSION",
    ".env.example",
    ".env.local.example",
    ".env.production.example",
    "templates\base.html",
    "templates\chat\shell.html",
    "static\app.js",
    "static\app.css",
    "static\chat.js",
    "desktop\main.js",
    "desktop\preload.js",
    "desktop\package.json",
    "mobile\android\app\build.gradle",
    "mobile\android\app\src\main\java\uz\rmes\app\MainActivity.java",
    "mobile\android\build_apk_linux.sh",
    "mobile\android\build_apk_windows.ps1",
    "mobile\ios\RMesIOS\AppConfig.swift",
    "mobile\ios\RMesIOS\Info.plist",
    "mobile\ios\RMesIOS\SceneDelegate.swift",
    "localgram\settings.py",
    "apps\chat\views.py"
)

if (!(Test-Path (Join-Path $ProjectRoot "manage.py"))) {
    throw "Не найден manage.py: $ProjectRoot"
}

Write-Host "[R-Messanger] Backup -> $BackupRoot" -ForegroundColor Cyan
foreach ($rel in $Files) {
    $src = Join-Path $PatchRoot $rel
    $dst = Join-Path $ProjectRoot $rel
    if (!(Test-Path $src)) { throw "В патче отсутствует: $rel" }
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
    Write-Host "[R-Messanger] Django check..." -ForegroundColor Cyan
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "manage.py check завершился с ошибкой" }
} else {
    Write-Host "[R-Messanger] .venv ещё не создан — Django check будет при следующем запуске." -ForegroundColor Yellow
}

Write-Host "" 
Write-Host "R-Messanger 15.1.2 установлен." -ForegroundColor Green
Write-Host "Backup: $BackupRoot"
Write-Host "Перезапусти сервер и нажми Ctrl+F5 в браузере."
