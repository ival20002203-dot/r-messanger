# R-Mes 15 security model

- Passwords use Django's password hashing; secrets belong in `.env`, never in source control.
- Admin/developer roles can require email OTP on every new login.
- Device sessions can be listed and revoked by the user; Developer has fleet-wide security controls.
- Presence privacy is enforced server-side, not only hidden by CSS/JavaScript.
- Uploads are size-limited and can pass antivirus, DLP and 18+ moderation before normal access.
- Call recordings are private admin artifacts and are never inserted into message history.
- Production traffic should use HTTPS/WSS only; TURN credentials must be changed from defaults.
- PostgreSQL/media backups and restore verification should run on a schedule.
- Prometheus/Zabbix endpoints must be protected by their configured token/network policy.
