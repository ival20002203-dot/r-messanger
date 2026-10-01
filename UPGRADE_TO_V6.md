# Upgrade Localgram v5 → v6

Короткий безопасный сценарий для текущего Windows стенда.

## 1. Backup

```powershell
cd "N:\VS CODE\localgram"
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v6.sql"
```

## 2. Stop

```powershell
docker compose stop web moderator securityworker
```

Если `securityworker` ещё отсутствует — просто продолжай.

Не выполнять:

```powershell
docker compose down -v
```

## 3. Replace source

Распаковать архив v6 в:

```text
N:\VS CODE\
```

с заменой файлов в `localgram`.

Сохранить:

```text
.env
media\
private_media\
backups\
```

## 4. Add v6 `.env` variables

Сравни текущий `.env` с `.env.example`.

Для локального Windows стенда:

```env
USE_S3_STORAGE=1
MINIO_ROOT_USER=localgram
MINIO_ROOT_PASSWORD=CHANGE_MINIO_PASSWORD
MINIO_BUCKET=localgram-media
MINIO_ENDPOINT=http://minio:9000
MINIO_PUBLIC_ENDPOINT=http://127.0.0.1:9000

CLAMAV_HOST=clamav
CLAMAV_PORT=3310
SECURITY_WORKER_SLEEP=1
DLP_ENABLED=1
DLP_MAX_PARSE_MB=25

ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=30

CONTENT_MODERATION_OCR_ENABLED=1
CONTENT_MODERATION_OCR_LANG=eng+rus
CONTENT_MODERATION_VIDEO_OCR_FRAMES=4
```

Не меняй существующий рабочий PostgreSQL password.

## 5. Build

```powershell
docker compose up -d --build
```

## 6. Migrations

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
docker compose exec web python manage.py showmigrations moderation
docker compose exec web python manage.py showmigrations securitycenter
```

v6 добавляет как минимум:

```text
accounts
[X] 0006_devices_tokens

chat
[X] 0005_localgram_v6
[X] 0006_search_index

moderation
[X] 0002_policy_categories

securitycenter
[X] 0001_initial
```

## 7. Copy old media into MinIO

```powershell
docker compose exec web python manage.py migrate_media_to_object_storage --dry-run
```

Если результат нормальный:

```powershell
docker compose exec web python manage.py migrate_media_to_object_storage
```

## 8. Doctor

```powershell
.\scripts\doctor_windows.ps1
```

## 9. Manual smoke test

Проверить:
- login / email OTP;
- direct chat;
- scroll/history;
- offline message reconnect;
- `@mention`;
- notification center;
- Saved Messages;
- folders;
- advanced search;
- upload file → сначала `Проверка файла`, затем доступен после ClamAV;
- Security Center;
- DLP case;
- moderation;
- device sessions;
- stickers;
- Audit 2.0;
- Control Center;
- MinIO Console.

Полная установка production и desktop client описаны в:

```text
docs/DEPLOYMENT_V6.md
```
