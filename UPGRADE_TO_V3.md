# Upgrade Localgram v2 → v3

This upgrade preserves the existing PostgreSQL volume.

## 1. Backup first

From your current Localgram directory:

```powershell
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v3.sql"
```

If your database/user names are different, use the values from `.env`.

## 2. Stop the web container

```powershell
docker compose stop web
```

Do **not** run:

```powershell
docker compose down -v
```

## 3. Preserve these items

Do not overwrite/delete:

```text
.env
media\
backups\
```

Your PostgreSQL data itself is in the Docker volume.

## 4. Replace source files with v3

Your working folder should remain:

```text
N:\VS CODE\localgram
```

The supplied ZIP uses `localgram\` as its top-level folder so it can be merged over the current project.

Keep the existing `.env`, `media\` and `backups\`.

The Compose file also pins the existing Docker volume names explicitly:

```text
localgram_localgram_postgres
localgram_localgram_redis
```

so a folder rename will not silently create a different database volume.

## 5. Check `.env`

v3 still uses the same PostgreSQL variables:

```env
POSTGRES_DB=localgram
POSTGRES_USER=localgram
POSTGRES_PASSWORD=YOUR_CURRENT_WORKING_DB_PASSWORD
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

Do not randomly change `POSTGRES_PASSWORD` after PostgreSQL has already initialized unless you also change the database role password.

SMTP must be configured for registration:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_HOST_USER=localgram@company.com
EMAIL_HOST_PASSWORD=YOUR_SMTP_PASSWORD
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=Localgram <localgram@company.com>
```

Optional login 2FA:

```env
LOGIN_EMAIL_2FA=0
```

Your bootstrap account becomes the protected developer role:

```env
BOOTSTRAP_ADMIN_EMAIL=your-admin@company.com
BOOTSTRAP_ADMIN_PASSWORD=YOUR_PASSWORD
BOOTSTRAP_ADMIN_NAME=Infrastructure Admin
```

## 6. Rebuild

```powershell
docker compose up -d --build
```

The entrypoint automatically runs:

```text
python manage.py migrate
python manage.py collectstatic
python manage.py bootstrap_localgram
```

## 7. Verify containers

```powershell
docker compose ps -a
```

Expected:

```text
db      Up (healthy)
redis   Up (healthy)
web     Up
```

## 8. Verify migrations

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
```

Expected:

```text
accounts
 [X] 0001_initial
 [X] 0002_localgram_v2
 [X] 0003_localgram_v3

chat
 [X] 0001_initial
 [X] 0002_localgram_v2
 [X] 0003_localgram_v3
```

## 9. Verify app

```text
http://127.0.0.1:8000/healthz/
```

Expected:

```json
{"status":"ok","service":"localgram"}
```

Optional one-command diagnostic after startup:

```powershell
.\scripts\doctor_windows.ps1
```

Then open:

```text
http://127.0.0.1:8000
```

and:

```text
http://127.0.0.1:8000/control/
```

## 10. Developer role

At startup `bootstrap_localgram` promotes the account from:

```env
BOOTSTRAP_ADMIN_EMAIL=...
```

to the `developer` role.

That role has the protected chat-copy behavior and developer-only forensic pages.

## If web starts restarting

Do not delete volumes.

Run:

```powershell
docker compose logs --tail=250 web
```

and diagnose the first traceback/error.
