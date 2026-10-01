# Upgrade to Artel Link v12.0.0

v12 adds the Windows/Desktop integration and the same PIN lock in the browser and Desktop client.

## Server upgrade

Keep the existing `.env` and Docker named volumes. Replace the application code, then run:

```bash
cd /opt/artel-link
docker compose up -d --build
```

The web startup applies migrations automatically. Verify:

```bash
docker compose exec web python manage.py showmigrations accounts | tail -12
docker compose exec web python manage.py check
docker compose ps -a
```

Expected new migration:

```text
[X] 0010_artel_link_app_lock
```

Do **not** run `docker compose down -v` during an upgrade because `-v` removes the named data volumes.

## PIN lock

After upgrade:

```text
Настройки → Конфиденциальность → Код-пароль Artel Link
```

The user enters the current account password, chooses a 4–8 digit PIN, selects an inactivity timeout, and optionally enables locking on each Desktop launch.

The PIN is stored only as a Django password hash in `UserPreference.app_lock_code_hash`.

## Desktop

The v12 Desktop source is in `desktop/` and defaults to:

```text
http://10.10.10.130:8000
```

On Windows run `desktop\build_windows.cmd` or `desktop\build_windows.ps1` to generate EXE + MSI.
