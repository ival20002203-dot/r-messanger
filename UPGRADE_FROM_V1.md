# Обновление Localgram v1 → v2 без потери БД

Эта версия специально содержит migrations `0002_localgram_v2.py`, которые рассчитаны на уже запущенную v1.

## 1. Сделать backup

Находясь в старой папке Localgram:

```powershell
.\scripts\backup_windows.ps1
```

Либо минимум PostgreSQL:

```powershell
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v2.sql"
```

## 2. НЕ удалять volumes

Можно остановить контейнеры:

```powershell
docker compose stop
```

Не выполнять:

```powershell
docker compose down -v
```

## 3. Сохранить старый `.env`

Новый архив содержит только `.env.example`.

Оставьте ваш существующий:

```text
.env
```

и добавьте в него новые параметры SMTP/OTP:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_HOST_USER=localgram@company.com
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=Localgram <localgram@company.com>

LOGIN_EMAIL_2FA=0
OTP_TTL_MINUTES=10
OTP_RESEND_SECONDS=60
OTP_MAX_ATTEMPTS=5
MAX_UPLOAD_MB=100
```

## 4. Заменить исходники

Можно заменить содержимое папки проекта файлами v2, но НЕ удаляйте:
- `.env`
- `media`
- `backups`

PostgreSQL находится в Docker volume и при обычной пересборке сохранится.

## 5. Пересобрать

```powershell
docker compose up -d --build
```

Entry point автоматически выполняет:

```text
python manage.py migrate
python manage.py collectstatic
python manage.py bootstrap_localgram
```

## 6. Проверить migrations

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
```

Нужно увидеть:

```text
accounts
 [X] 0001_initial
 [X] 0002_localgram_v2

chat
 [X] 0001_initial
 [X] 0002_localgram_v2
```

## 7. Проверить приложение

```powershell
docker compose ps -a
docker compose logs --tail=200 web
```

Затем:

```text
http://127.0.0.1:8000/healthz/
```

Ответ:

```json
{"status":"ok","service":"localgram"}
```

## 8. Настроить и проверить SMTP

Открыть:

```text
Control Center → Системные настройки → Проверка SMTP
```

Отправить тестовое письмо.

После этого новая регистрация работает строго:

```text
форма → письмо → код → аккаунт
```
