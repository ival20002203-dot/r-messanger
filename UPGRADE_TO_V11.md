# Artel Link 11.0.0 — обновление

## Перед обновлением
Сохраните `.env`, `media/`, `private_media/`, `backups/` и сделайте backup PostgreSQL. Не используйте `docker compose down -v`.

## Windows / Docker
```powershell
cd "N:\VS CODE\localgram"
docker compose up -d --build
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\doctor_windows.ps1
```

Проверьте migrations:
```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations operations
```
Ожидаются:
```text
[X] 0009_artel_link_appearance
[X] 0003_artel_link_v11_client_policy
```

## Desktop
```powershell
cd "N:\VS CODE\localgram\desktop"
npm.cmd install
npm.cmd run dist:win
```
Получите `dist\ArtelLink-11.0.0-Setup.exe`.

Для GPO:
```powershell
npm.cmd run dist:gpo
```

## Почему раньше открывался браузер
Desktop мог загрузить локальный fallback `http://127.0.0.1:8000`, но проверка внутренних ссылок сравнивала URL только с корпоративным `https://artellink.artelgroup.org`. Поэтому локальная ссылка ошибочно считалась внешней и отправлялась в системный браузер. В 11.0.0 разрешены active/configured/default/fallback origins, поэтому навигация остаётся внутри Desktop-клиента.
