# R-Mes 15 — .env коротко

## Локально через VS Code

`.\scripts\run_dev_vscode.ps1` сам создаёт `.env` из `.env.local.example`.

Главное для тестов:

```env
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
CORP_EMAIL_DOMAINS=test.com,rmes.local
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
PUSH_ENABLED=0
```

Код подтверждения почты будет печататься в терминале.

## Public VPS

Берите `.env.production.example` и обязательно меняйте:

```env
SECRET_KEY=...
POSTGRES_PASSWORD=...
MINIO_ROOT_PASSWORD=...
TURN_PASSWORD=...
BOOTSTRAP_ADMIN_EMAIL=...
BOOTSTRAP_ADMIN_PASSWORD=...
R_MES_SERVER_NAME=...
FILES_SERVER_NAME=...
ALLOWED_HOSTS=...
CSRF_TRUSTED_ORIGINS=https://...
TURN_HOST=PUBLIC_IP
ACME_EMAIL=...
```

`scripts/prepare_public_vps.sh` генерирует основные случайные секреты автоматически.

## Push Android

```env
PUSH_ENABLED=1
FCM_PROJECT_ID=my-firebase-project
FCM_SERVICE_ACCOUNT_FILE=/run/secrets/firebase-service-account.json
```

Плюс `google-services.json` в Android-проекте.

## Push iPhone

```env
PUSH_ENABLED=1
APNS_KEY_FILE=/run/secrets/AuthKey_XXXX.p8
APNS_KEY_ID=XXXX
APNS_TEAM_ID=XXXXXXXXXX
APNS_BUNDLE_ID=uz.rmes.ios
APNS_USE_SANDBOX=0
```

## TURN

```env
TURN_ENABLED=1
TURN_HOST=PUBLIC_IP
TURN_USERNAME=rmes
TURN_PASSWORD=LONG_RANDOM_PASSWORD
```

На firewall откройте UDP/TCP 3478 и UDP 49160-49200.

## 18+

```env
CONTENT_MODERATION_ENABLED=1
CONTENT_MODERATION_MEDIA_ENABLED=1
CONTENT_MODERATION_TEXT_ENABLED=1
```

## Admin 2FA

```env
ADMIN_EMAIL_2FA_REQUIRED=1
```

Админские роли будут требовать e-mail OTP даже если обычным пользователям login-2FA выключен.
