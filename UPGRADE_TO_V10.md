# Upgrade to Artel Link 10.0.0

## Safe upgrade

1. Back up the current database/media.
2. Replace application source files, but keep your working `.env`, backups and persistent Docker volumes.
3. Rebuild and start:

```powershell
docker compose up -d --build
```

4. Verify migrations:

```powershell
docker compose exec web python manage.py showmigrations accounts
docker compose exec web python manage.py showmigrations chat
docker compose exec web python manage.py showmigrations operations
```

Expected new migration:

```text
operations
[X] 0002_artel_link_v10_client_policy
```

5. Run doctor:

```powershell
.\scripts\doctor_windows.ps1
```

## Desktop

```powershell
cd desktop
.\build_windows.ps1
```

The product name, installer name, taskbar/tray branding and deep-link protocol are now Artel Link.

## Calls

For a purely routed corporate LAN, browsers can often connect directly using host ICE candidates. For VPN/NAT/segmented networks, configure an internal STUN/TURN service and set for example:

```env
RTC_ICE_SERVERS_JSON=[{"urls":["turn:turn.artelgroup.org:3478"],"username":"artellink","credential":"CHANGE_ME"}]
```

Do not use a public STUN/TURN dependency for a strictly internal deployment.
