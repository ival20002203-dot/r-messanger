$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-PythonCommand {
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3.12') },
        @{ Exe = 'py'; Args = @('-3.11') },
        @{ Exe = 'py'; Args = @() },
        @{ Exe = 'python'; Args = @() }
    )

    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Exe -ErrorAction SilentlyContinue) {
            try {
                & $candidate.Exe @($candidate.Args) --version *> $null
                if ($LASTEXITCODE -eq 0) {
                    return $candidate
                }
            }
            catch { }
        }
    }

    throw 'Python not found. Install Python 3.12 x64 and enable Add Python to PATH.'
}

if (!(Test-Path '.env')) {
    if (!(Test-Path '.env.local.example')) {
        throw '.env.local.example not found in the project root.'
    }
    Copy-Item '.env.local.example' '.env'
    Write-Host '[R-Mes] Created .env from .env.local.example' -ForegroundColor Cyan
}

if (!(Test-Path '.venv')) {
    $PythonCommand = Get-PythonCommand
    Write-Host '[R-Mes] Creating Python virtual environment...' -ForegroundColor Cyan
    & $PythonCommand.Exe @($PythonCommand.Args) -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

$Version = & $Python --version 2>&1
Write-Host "[R-Mes] Using $Version" -ForegroundColor DarkGray

Write-Host '[R-Mes] Installing/updating dependencies...' -ForegroundColor Cyan
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

Write-Host '[R-Mes] Applying migrations...' -ForegroundColor Cyan
& $Python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed.' }

Write-Host '[R-Mes] Preparing local developer account...' -ForegroundColor Cyan
& $Python manage.py bootstrap_localgram
if ($LASTEXITCODE -ne 0) { throw 'Local bootstrap failed.' }

Write-Host '[R-Mes] Checking environment...' -ForegroundColor Cyan
& $Python manage.py rmes_env_check
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed.' }

Write-Host ''
Write-Host '=============================================' -ForegroundColor DarkCyan
Write-Host ' R-Mes: http://127.0.0.1:8000' -ForegroundColor Green
Write-Host ' Login: developer@rmes.local' -ForegroundColor Green
Write-Host ' Password: RMesLocal-2026-Dev!' -ForegroundColor Green
Write-Host ' Ctrl+C = stop server' -ForegroundColor DarkGray
Write-Host '=============================================' -ForegroundColor DarkCyan
Write-Host ''

& $Python manage.py runserver 127.0.0.1:8000
