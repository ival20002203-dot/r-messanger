# R-Mes 15 architecture

## Clients

Windows Electron, Android native shell, iOS native shell and browser clients share the authenticated R-Mes web/API/WebSocket surface. Native clients add OS permissions, push tokens, deep links, splash/offline handling and app installation.

## Realtime

Django 5.2 + Channels/Daphne provide HTTP and WebSocket traffic. Redis is the channel layer in production. Presence uses short active leases plus heartbeat/visibility signals so stale sessions expire quickly.

## Data

PostgreSQL stores accounts, conversations, messages, receipts, sessions, moderation/audit data and call metadata. MinIO stores production media. Private call recordings use authenticated server access and are visible only in Developer Control Center.

## Security and moderation

ClamAV scans files, DLP inspects supported documents, NudeNet/media workers flag 18+ content, audit logs record administrative actions, and rate limits/anti-spam protect high-risk endpoints.

## Calls

WebRTC handles audio. Signaling runs through R-Mes WebSocket/HTTP events. coturn provides TURN relay for users behind NAT/CGNAT. Recording is a compliance/admin artifact, not a chat message.

## Production edge

Caddy provides automatic HTTPS. Nginx proxies/load-balances two Daphne instances and the file endpoint. PostgreSQL, Redis, MinIO, ClamAV, moderation/security workers and scheduler run as Docker services.
