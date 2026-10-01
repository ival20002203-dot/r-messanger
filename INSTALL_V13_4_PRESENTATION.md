# Artel Link 13.4.0 — presentation install

1. Preserve the live `.env` before replacing code.
2. Copy the full `localgram/` tree over `/opt/artel-link/`.
3. Restore the preserved `.env`.
4. Run `bash scripts/prepare_presentation.sh` once. It enables presentation moderation/TURN flags, runs migrations, repairs old attachment/moderation queues, and recreates the relevant services without deleting volumes.
5. If UFW is enabled, run `bash scripts/enable_call_ports.sh`.
6. Run `bash scripts/presentation_check.sh`.
7. Build/install Desktop 13.4.0 for native branded notifications and reliable media permissions over the current HTTP test origin.

Never run `docker compose down -v` during an upgrade.
