param(
    [string]$ServerIp = '127.0.0.1',
    [string]$AdminEmail = 'developer@rmes.local'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function New-RMesSecret([int]$Bytes = 24) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).Replace('/', '_').Replace('+', '-').TrimEnd('=')
}

$ServerUrl = if ($ServerIp -match '^https?://') {
    $ServerIp.TrimEnd('/')
}
else {
    "http://${ServerIp}:8000"
}

$HostName = ([uri]$ServerUrl).Host
$BootstrapPassword = "$(New-RMesSecret 18)Aa1!"

$EnvContent = @"
SECRET_KEY=$(New-RMesSecret 48)
DEBUG=0
ALLOWED_HOSTS=$HostName,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=$ServerUrl
R_MES_URL=$ServerUrl
WEB_ACCESS_ENABLED=1
POSTGRES_DB=rmes
POSTGRES_USER=rmes
POSTGRES_PASSWORD=$(New-RMesSecret 28)
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
USE_S3_STORAGE=1
MINIO_ROOT_USER=rmes
MINIO_ROOT_PASSWORD=$(New-RMesSecret 28)
MINIO_BUCKET=rmes-media
MINIO_ENDPOINT=http://minio:9000
TURN_ENABLED=1
TURN_HOST=$HostName
TURN_USERNAME=rmes
TURN_PASSWORD=$(New-RMesSecret 28)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
LOGIN_EMAIL_2FA=0
BOOTSTRAP_ADMIN_EMAIL=$AdminEmail
BOOTSTRAP_ADMIN_PASSWORD=$BootstrapPassword
"@

Set-Content -Path '.env' -Value $EnvContent -Encoding UTF8
Write-Host 'Created .env' -ForegroundColor Green

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or is not available in PATH.'
}

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed.' }

docker compose exec web python manage.py rmes_env_check
if ($LASTEXITCODE -ne 0) { throw 'R-Mes environment check failed.' }

Write-Host ''
Write-Host "R-Mes server: $ServerUrl" -ForegroundColor Green
Write-Host "Admin email: $AdminEmail" -ForegroundColor Yellow
Write-Host "Temporary password: $BootstrapPassword" -ForegroundColor Yellow
Write-Host 'Change this password after the first login.' -ForegroundColor Yellow
