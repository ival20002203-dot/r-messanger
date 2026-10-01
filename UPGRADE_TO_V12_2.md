# Artel Link 12.2.0

## Added
- Quick lock icon above the chat list, similar to Telegram.
- Clicking the lock immediately opens the existing Artel Link PIN lock.
- If PIN is not configured, the lock icon opens Settings → Privacy.
- Full categorized Unicode emoji picker with recent emoji history.
- Expanded quick reactions.

## Server update
1. Keep the existing `.env` and Docker volumes.
2. Copy the v12.2 patch over `/opt/artel-link/`.
3. Run `docker compose up -d --build`.
4. Hard refresh browser or fully restart Desktop.

No database migration is required from 12.1.0 to 12.2.0.
Do not use `docker compose down -v` during an upgrade.
