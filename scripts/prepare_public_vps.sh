#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: sudo ./scripts/prepare_public_vps.sh <domain-or-ip.nip.io> <public-ip> [admin-email]"
  exit 1
fi
DOMAIN="$1"
PUBLIC_IP="$2"
ADMIN_EMAIL="${3:-developer@rmes.local}"
ACME_EMAIL="${ADMIN_EMAIL}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io curl openssl
  apt-get install -y docker-compose-v2 || apt-get install -y docker-compose-plugin
  systemctl enable --now docker
fi

if [[ ! -f .env ]]; then cp .env.production.example .env; fi
BOOTSTRAP_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(22)+"Aa1!")')"
python3 - "$DOMAIN" "$PUBLIC_IP" "$ACME_EMAIL" "$ADMIN_EMAIL" "$BOOTSTRAP_PASSWORD" <<'PY'
from pathlib import Path
import secrets,sys,re
p=Path('.env'); s=p.read_text()
domain,ip,email,admin_email,admin_password=sys.argv[1:6]
files='files.'+domain
admin_domain=admin_email.split('@',1)[1].lower() if '@' in admin_email else 'rmes.local'
replacements={
'DEBUG':'0','ALLOWED_HOSTS':f'{domain},{files}','CSRF_TRUSTED_ORIGINS':f'https://{domain}',
'SECURE_SSL_REDIRECT':'1','R_MES_SERVER_NAME':domain,'FILES_SERVER_NAME':files,'R_MES_URL':f'https://{domain}',
'MINIO_PUBLIC_ENDPOINT':f'https://{files}','TURN_HOST':ip,'ACME_EMAIL':email,
'POSTGRES_PASSWORD':secrets.token_urlsafe(32),'MINIO_ROOT_PASSWORD':secrets.token_urlsafe(32),
'TURN_PASSWORD':secrets.token_urlsafe(32),'METRICS_TOKEN':secrets.token_urlsafe(32),
'SECRET_KEY':secrets.token_urlsafe(64),'BOOTSTRAP_ADMIN_EMAIL':admin_email,
'BOOTSTRAP_ADMIN_PASSWORD':admin_password,'BOOTSTRAP_ADMIN_NAME':'R-Mes Developer',
'CORP_EMAIL_DOMAINS':f'{admin_domain},test.com,rmes.local',
# Until SMTP is configured, OTP messages can be read from web container logs.
'EMAIL_BACKEND':'django.core.mail.backends.console.EmailBackend','LOGIN_EMAIL_2FA':'0',
}
for k,v in replacements.items():
    pat=re.compile(rf'(?m)^{re.escape(k)}=.*$')
    if pat.search(s): s=pat.sub(f'{k}={v}',s)
    else: s+=f'\n{k}={v}'
p.write_text(s+'\n')
PY

usermod -aG docker "${SUDO_USER:-root}" 2>/dev/null || true

docker compose -f docker-compose.prod.yml up -d --build
./scripts/install_backup_cron.sh

echo
printf '\033[1;36mR-Mes: https://%s\033[0m\n' "$DOMAIN"
echo "Developer: $ADMIN_EMAIL"
echo "Temporary password: $BOOTSTRAP_PASSWORD"
echo "Change it after first login."
echo "If admin OTP is requested before SMTP is configured: docker compose -f docker-compose.prod.yml logs -f web1"
echo "Check: docker compose -f docker-compose.prod.yml ps"
echo "Remember cloud firewall: TCP 22/80/443/3478 and UDP 443/3478/49160-49200."
