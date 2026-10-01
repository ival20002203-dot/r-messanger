# Localgram v6 — установка и запуск

## A. Обновление текущего Windows стенда

Текущий путь:

```text
N:\VS CODE\localgram
```

### 1. Backup

```powershell
cd "N:\VS CODE\localgram"
.\scripts\backup_windows.ps1
```

Если старый проект ещё не содержит v6 backup script, перед заменой хотя бы сделай DB backup:

```powershell
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v6.sql"
```

### 2. Остановить application containers

```powershell
docker compose stop web moderator securityworker
```

Если `securityworker` ещё не существует, ошибка для него не страшна.

**Не выполнять:**

```powershell
docker compose down -v
```

### 3. Распаковать v6

Архив содержит папку:

```text
localgram\
```

Распаковать в:

```text
N:\VS CODE\
```

с заменой исходников.

Сохранить текущие:

```text
.env
media\
private_media\
backups\
```

### 4. Дополнить `.env`

Возьми новые переменные из `.env.example`. Минимально для v6:

```env
USE_S3_STORAGE=1
MINIO_ROOT_USER=localgram
MINIO_ROOT_PASSWORD=CHANGE_MINIO_PASSWORD
MINIO_BUCKET=localgram-media
MINIO_ENDPOINT=http://minio:9000
MINIO_PUBLIC_ENDPOINT=http://127.0.0.1:9000

CLAMAV_HOST=clamav
CLAMAV_PORT=3310
DLP_ENABLED=1
DLP_MAX_PARSE_MB=25

ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=30

CONTENT_MODERATION_OCR_ENABLED=1
CONTENT_MODERATION_OCR_LANG=eng+rus
CONTENT_MODERATION_VIDEO_OCR_FRAMES=4
```

Не меняй работающий `POSTGRES_PASSWORD`, если база уже инициализирована.

### 5. Build / start

```powershell
docker compose up -d --build
```

Теперь локальный профиль содержит:

```text
db
redis
minio
minio-init
clamav
web
moderator
securityworker
```

### 6. Перенести старые local media в MinIO

Сначала dry-run:

```powershell
docker compose exec web python manage.py migrate_media_to_object_storage --dry-run
```

Потом реальное копирование:

```powershell
docker compose exec web python manage.py migrate_media_to_object_storage
```

Команда **не меняет имена FileField в PostgreSQL** — она переносит существующие файлы с теми же object keys.

### 7. Полная диагностика

```powershell
.\scripts\doctor_windows.ps1
```

### 8. URL

```text
Localgram:       http://127.0.0.1:8000
MinIO API:       http://127.0.0.1:9000
MinIO Console:   http://127.0.0.1:9001
Control Center:  http://127.0.0.1:8000/control/
Security Center: http://127.0.0.1:8000/control/security/
```

---

# B. Один production Linux сервер

Рекомендуемый путь:

```text
/opt/localgram
```

## 1. DNS

Создать:

```text
localgram.company.local  → server/LB IP
files.localgram.company.local → server/LB IP
```

## 2. Docker

Ubuntu:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

Перелогиниться в SSH/session.

## 3. Проект

```bash
sudo mkdir -p /opt/localgram
sudo chown "$USER":"$USER" /opt/localgram
cd /opt/localgram
```

Скопировать содержимое архива сюда.

## 4. Environment

```bash
cp .env.production.example .env
nano .env
```

Обязательно поменять:

```text
SECRET_KEY
POSTGRES_PASSWORD
MINIO_ROOT_PASSWORD
BOOTSTRAP_ADMIN_EMAIL
BOOTSTRAP_ADMIN_PASSWORD
SMTP credentials
host names
```

## 5. TLS

Предпочтительный корпоративный вариант:

```text
Client HTTPS
   ↓
F5 / HAProxy / reverse proxy (TLS termination)
   ↓
Localgram Nginx :80
```

Load balancer должен передавать:

```text
Host
X-Forwarded-For
X-Forwarded-Proto: https
Upgrade / Connection для WebSocket
```

Не публикуй PostgreSQL, Redis, MinIO internal API, PgBouncer и ClamAV наружу.

## 6. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Production profile:

```text
nginx
web1
web2
pgbouncer
db
redis
minio
minio-init
clamav
moderator
securityworker
migrate (one-shot)
```

## 7. Existing media upgrade

Если переносишь старый Localgram:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate \
  python manage.py migrate_media_to_object_storage --dry-run
```

потом:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate \
  python manage.py migrate_media_to_object_storage
```

## 8. Check

```bash
chmod +x scripts/doctor_linux.sh scripts/backup_linux.sh
./scripts/doctor_linux.sh
```

Health check:

```bash
curl -fsS -H "Host: localgram.company.local" http://127.0.0.1/healthz/
```

## 9. Firewall

На самом Localgram host разрешить только необходимые management порты и frontend:

```text
22/tcp   SSH — только admin network
80/tcp   from corporate LB/network
443/tcp  если TLS завершается на этом host
```

Internal Docker service ports не публикуются production compose наружу.

---

# C. Реальная multi-node HA

Для отказа **целого application host**, а не только контейнера:

```text
LB
├── App node A :8080
└── App node B :8080
        ↓
PostgreSQL HA endpoint
Redis HA endpoint
Distributed MinIO/S3
Shared private evidence filesystem
```

Использовать:

```text
docker-compose.app-node.yml
infrastructure/ha/README.md
```

На обеих app nodes:

```bash
docker compose -f docker-compose.app-node.yml up -d --build
```

Проверка load balancer:

```text
GET /healthz/
```

Migrations выполнять **один раз на релиз**, а не одновременно на каждой ноде.

---

# D. Desktop client

Source:

```text
desktop\
```

На Windows development PC:

```powershell
cd desktop
npm install
$env:LOCALGRAM_URL="https://localgram.company.local"
npm start
```

Installer:

```powershell
npm run dist:win
```

Результат:

```text
desktop\dist\Localgram-6.0.0-Setup.exe
```

Desktop app:
- tray;
- minimize to tray;
- OS autostart option;
- secure Electron sandbox;
- microphone/camera/notifications;
- offline screen;
- unread tray count.

---

# E. Backup

Windows:

```powershell
.\scripts\backup_windows.ps1
```

Linux:

```bash
./scripts/backup_linux.sh
```

Backup должен включать:

```text
PostgreSQL dump
MinIO data
private moderation evidence
.env — отдельно в защищённом secret backup
```

Для production рекомендуется дополнительно использовать PostgreSQL PITR/WAL archive и MinIO replication/versioning.
