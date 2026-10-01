# Localgram v3 → v4 — обновление без удаления базы

v4 содержит новую migration:

```text
chat 0004_localgram_v4
```

Она добавляет только личные настройки оформления чата. Существующие пользователи, сообщения, файлы и forensic-история сохраняются.

## 1. Сделать backup PostgreSQL

Из текущей папки проекта:

```powershell
cd "N:\VS CODE\localgram"
New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
cmd /c "docker compose exec -T db pg_dump -U localgram localgram > backups\before_v4.sql"
```

Если `POSTGRES_USER` или `POSTGRES_DB` у вас другие — используйте значения из `.env`.

## 2. Остановить web

```powershell
docker compose stop web
```

Не выполнять:

```powershell
docker compose down -v
```

`-v` удаляет Docker volumes.

## 3. Сохранить

Не удаляйте:

```text
.env
media\
backups\
```

PostgreSQL volume тоже должен остаться:

```text
localgram_localgram_postgres
```

## 4. Заменить исходники файлами v4

Архив содержит папку:

```text
localgram\
```

Её можно распаковать в:

```text
N:\VS CODE\
```

с объединением/заменой файлов текущего проекта.

Ваш существующий `.env` оставьте.

## 5. Пересобрать

```powershell
cd "N:\VS CODE\localgram"
docker compose up -d --build
```

Entry point выполнит:

```text
python manage.py migrate
python manage.py collectstatic
python manage.py bootstrap_localgram
```

## 6. Проверить статус

```powershell
docker compose ps -a
```

Нужно:

```text
db       Up ... healthy
redis    Up ... healthy
web      Up ...
```

## 7. Проверить migration

```powershell
docker compose exec web python manage.py showmigrations chat
```

Должно быть:

```text
[X] 0001_initial
[X] 0002_localgram_v2
[X] 0003_localgram_v3
[X] 0004_localgram_v4
```

Accounts:

```powershell
docker compose exec web python manage.py showmigrations accounts
```

Должно оставаться:

```text
[X] 0001_initial
[X] 0002_localgram_v2
[X] 0003_localgram_v3
```

## 8. Запустить полную диагностику

```powershell
.\scripts\doctor_windows.ps1
```

## 9. Проверить вручную

Откройте:

```text
http://127.0.0.1:8000
```

Проверить:

1. Открыть длинный чат.
2. Колесо мыши / touchpad должны прокручивать только историю.
3. Верхняя панель остаётся сверху.
4. Поле ввода всегда остаётся снизу.
5. Уйти вверх — появляется кнопка `↓`.
6. Дойти до начала — автоматически подгружаются более старые сообщения.
7. Нажать `Esc` — чат красиво закрывается.
8. `Ctrl+F` — поиск в открытом чате.
9. `Ctrl+K` — фокус на глобальный поиск.
10. В настройках профиля установить `@username`.
11. Найти пользователя как `username` и как `@username`.
12. Открыть настройки чата и выбрать цвет/фон.
13. Проверить `/control/`.

## Если web перезапускается

Не удаляйте volume.

Выполните:

```powershell
docker compose logs --tail=250 web
```

Диагностировать нужно первую реальную ошибку/Traceback.
