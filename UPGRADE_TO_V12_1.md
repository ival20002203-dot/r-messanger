# Artel Link 12.1.0

## Added
- Browser UI can be disabled with `WEB_ACCESS_ENABLED=0` while Artel Link Desktop keeps working.
- Desktop sends `X-Artel-Link-Desktop: 1` on browser and Node-side connectivity/version checks.
- Friendly browser-disabled page and friendly access-denied pages.
- One-command scripts: `scripts/web_off.sh`, `scripts/web_on.sh`, `scripts/web_status.sh`.
- Sidebar branding strip removed as requested.

## Server update
1. Keep your existing `.env` and Docker volumes.
2. Copy the patch over `/opt/artel-link/`.
3. Add `WEB_ACCESS_ENABLED=1` or `0` to `.env`.
4. Run `docker compose up -d --build`.

## Toggle
```bash
cd /opt/artel-link
bash scripts/web_off.sh   # browser OFF, Desktop ON
bash scripts/web_on.sh    # browser ON, Desktop ON
bash scripts/web_status.sh
```

Do not use `docker compose down -v` during an upgrade.
