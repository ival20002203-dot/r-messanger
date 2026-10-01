# Localgram v6 → v7

This upgrade is non-destructive. Existing PostgreSQL, Redis, MinIO and moderation evidence are retained.

## 1. Backup current v6

```powershell
cd "N:\VS CODE\localgram"
.\scripts\backup_windows.ps1
```

At minimum confirm a new file exists:

```text
backups\db_YYYYMMDD_HHMMSS.sql
```

## 2. Stop application containers

```powershell
docker compose stop web moderator securityworker
```

Do **not** run:

```powershell
docker compose down -v
```

## 3. Replace source

Extract the v7 archive into:

```text
N:\VS CODE\
```

The archive contains top-level folder:

```text
localgram\
```

Keep your current:

```text
.env
media\
private_media\
backups\
```

## 4. Add v7 environment variables

Append to your existing `.env`:

```env
METRICS_ENABLED=1
METRICS_TOKEN=CHANGE_RANDOM_METRICS_TOKEN
RATE_LIMIT_ENABLED=1
RATE_LIMIT_LOGIN=10
RATE_LIMIT_SEARCH=120
RATE_LIMIT_UPLOAD=30
RATE_LIMIT_MESSAGES=80
ANTI_SPAM_ENABLED=1
ANTI_SPAM_DUPLICATE_LIMIT=8
ANTI_SPAM_WINDOW_SECONDS=60
FILE_PREVIEW_MAX_MB=25
SCHEDULED_POST_WORKER_SLEEP=2
CLIENT_UPDATE_API_PUBLIC=1
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE_GRAFANA_PASSWORD
```

Do not change the existing working `POSTGRES_PASSWORD`.

## 5. Start v7

```powershell
cd "N:\VS CODE\localgram"
docker compose up -d --build
```

v7 local services:

```text
db
redis
minio
minio-init
clamav
web
moderator
securityworker
scheduler
```

## 6. Verify migrations

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
docker compose exec web python manage.py showmigrations moderation
docker compose exec web python manage.py showmigrations securitycenter
docker compose exec web python manage.py showmigrations operations
```

Important new migrations:

```text
accounts
[X] 0007_rbac_device_trust

chat
[X] 0007_polls_scheduled_posts

operations
[X] 0001_initial
```

## 7. Run Doctor

```powershell
.\scripts\doctor_windows.ps1
```

Do not continue to real users if Django check, DB, Redis, MinIO, ClamAV or migrations fail.

## 8. Smoke test

Open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/control/
http://127.0.0.1:8000/control/infrastructure/
http://127.0.0.1:8000/control/security/
http://127.0.0.1:8000/control/rbac/
http://127.0.0.1:8000/control/backups/
http://127.0.0.1:8000/control/client-versions/
```

Check:
- normal message;
- file upload and ClamAV state;
- PDF/DOCX/XLSX/PPTX preview;
- poll creation/voting;
- scheduled channel post;
- custom RBAC role;
- device Trusted/Suspicious/Blocked;
- developer devices remain invisible to non-developer admins;
- Security Center rate-limit feed.

## 9. Monitoring on Windows/dev

Make the token file equal to `METRICS_TOKEN`:

```powershell
$token = "CHANGE_RANDOM_METRICS_TOKEN"
Set-Content .\infrastructure\prometheus\metrics_token $token -Encoding ASCII
```

Then:

```powershell
docker compose -f docker-compose.yml -f docker-compose.monitoring.dev.yml up -d --build
```

Open:

```text
Prometheus http://127.0.0.1:9090
Grafana    http://127.0.0.1:3000
```

## 10. Verify a restore

After creating a fresh backup:

```powershell
.\scripts\backup_windows.ps1
.\scripts\restore_test_windows.ps1
```

Result appears in:

```text
/control/backups/
```

## 11. Desktop v7

```powershell
cd "N:\VS CODE\localgram\desktop"
npm install
$env:LOCALGRAM_URL="http://127.0.0.1:8000"
npm start
```

Installer:

```powershell
npm run dist:win
```

Auto-update is enabled for packaged builds when `LOCALGRAM_UPDATE_URL` points to an internal electron-builder generic update feed.
