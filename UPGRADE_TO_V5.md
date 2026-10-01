# Localgram v4 → v5

Обновление сохраняет существующую PostgreSQL-базу, сообщения, файлы и forensic-историю.

Новые migrations:

```text
accounts
  0004_reserved_username
  0005_seed_reserved_usernames

moderation
  0001_initial
```

## 1. Backup

```powershell
cd "N:\VS CODE\localgram"
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v5.sql"
```

Если `POSTGRES_USER` / `POSTGRES_DB` отличаются — возьми их из `.env`.

## 2. Остановить web

```powershell
docker compose stop web
```

Не использовать:

```powershell
docker compose down -v
```

## 3. Сохранить

Не перезаписывать своими старыми копиями:

```text
.env
media\
private_media\
backups\
```

`private_media\` содержит developer-only moderation evidence и с v5 должен входить в backup.

PostgreSQL volume остаётся:

```text
localgram_localgram_postgres
```

## 4. Распаковать v5

Архив содержит:

```text
localgram\
```

Распаковать в:

```text
N:\VS CODE\
```

с объединением файлов проекта.

Оставь текущий `.env`, затем добавь новые параметры:

```env
CONTENT_MODERATION_ENABLED=1
CONTENT_MODERATION_TEXT_ENABLED=1
CONTENT_MODERATION_MEDIA_ENABLED=1
CONTENT_MODERATION_THRESHOLD=0.62
CONTENT_MODERATION_VIDEO_FRAMES=10
CONTENT_MODERATION_WORKER_SLEEP=1.5
CONTENT_MODERATION_POLICY_NOTICE=Отправленный контент может автоматически анализироваться средствами корпоративной модерации и сохраняться для проверки уполномоченными администраторами.
```

## 5. Rebuild

```powershell
docker compose up -d --build
```

Теперь должны быть четыре контейнера:

```text
db
redis
web
moderator
```

## 6. Проверить

```powershell
docker compose ps -a
```

Ожидается:

```text
db         Up / healthy
redis      Up / healthy
web        Up
moderator  Up
```

## 7. Migrations

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
docker compose exec web python manage.py showmigrations moderation
```

Accounts:

```text
[X] 0001_initial
[X] 0002_localgram_v2
[X] 0003_localgram_v3
[X] 0004_reserved_username
[X] 0005_seed_reserved_usernames
```

Chat:

```text
[X] 0001_initial
[X] 0002_localgram_v2
[X] 0003_localgram_v3
[X] 0004_localgram_v4
```

Moderation:

```text
[X] 0001_initial
```

## 8. Doctor

```powershell
.\scripts\doctor_windows.ps1
```

Он проверяет:
- Django;
- PostgreSQL;
- Redis;
- migrations;
- developer;
- reserved usernames;
- NudeNet import;
- moderation queue;
- web logs;
- moderator logs.

## 9. Что проверить в UI

```text
/control/usernames/
/control/moderation/
/auth/profile/
```

### Username

В `/control/usernames/` должны быть примерно 2334 built-in записей, автоматически защищённых migration-ом.

### Moderation

Отправь тестовую безопасную картинку — moderation case не должен создаваться.

Для настройки/тестирования самого детектора используй контролируемые тестовые материалы вашей организации, а не случайный публичный контент.

### Profile

Измени имя/bio/@username:
- справа появляется floating save dock;
- примерно через секунду сохраняется автоматически;
- ✓ сохраняет сразу;
- при быстром выходе появляется окно Save / Leave / Stay.

## Если moderator перезапускается

```powershell
docker compose logs --tail=250 moderator
```

## Если web перезапускается

```powershell
docker compose logs --tail=250 web
```

Не удаляй Docker volumes для исправления обычной ошибки приложения.
