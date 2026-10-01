$ErrorActionPreference = "Stop"
if (!(Test-Path ".venv")) { py -3.12 -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
if (!(Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Создан .env. Настрой SMTP и пароли." -ForegroundColor Yellow
}
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py bootstrap_localgram
daphne -b 0.0.0.0 -p 8000 localgram.asgi:application
