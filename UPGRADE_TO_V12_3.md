# Artel Link 12.3.0

## Added
- Back arrow on registration step 1.
- Back arrow on registration verification step 2.
- Returning from step 2 restores corporate email and display name so the user can correct them before requesting a new code.
- Password fields are intentionally blank on return and must be re-entered.
- Back arrow on login OTP verification.

## Server update
1. Keep the existing `.env` and Docker volumes.
2. Copy the v12.3 patch over `/opt/artel-link/`.
3. Run `docker compose up -d --build web`.
4. Hard refresh browser or fully restart Desktop.

No database migration is required from 12.2.0 to 12.3.0.
Do not use `docker compose down -v` during an upgrade.
