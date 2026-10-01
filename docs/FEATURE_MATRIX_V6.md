# Localgram v6 feature matrix

| Area | v6 |
|---|---|
| Mentions `@username`, `@all` | Yes |
| Notification Center | Yes |
| Per-chat mute 1h / 8h / permanent | Yes |
| Sent / delivered / read receipts | Yes |
| Group receipt viewer | Yes |
| Saved Messages | Yes |
| Multiple pinned messages | Yes |
| Smart/custom chat folders | Yes |
| PostgreSQL full-text search | Yes |
| Search `from:`, `after:`, `before:`, `has:` | Yes |
| Media / Files / Links / Voice tabs | Yes |
| MinIO object storage | Yes |
| Existing local-media migration command | Yes |
| ClamAV quarantine pipeline | Yes |
| DLP monitor-only cases | Yes |
| DLP secret masking | Yes |
| Expanded moderation + OCR policy signals | Yes |
| Device/session registry | Yes |
| Developer device-session hiding | Yes |
| Desktop Electron client source | Yes |
| Access/refresh native tokens | Yes |
| Token-authenticated WebSocket | Yes |
| Push-token registration foundation | Yes |
| Browser offline message queue | Yes, text messages |
| Server idempotency (`client_message_id`) | Yes |
| App process HA (`web1`,`web2`,`nginx`) | Yes |
| Multi-node HA app profile | Yes |
| PgBouncer | Yes |
| Audit 2.0 + CSV export | Yes |
| Security Center / risk score | Yes |
| Microinteractions / View Transitions | Yes |
| SPA-like prefetch navigation | Yes |
| Custom sticker packs / custom emoji flag | Yes |
| Realtime reconnect user banners/toasts | Removed |
| PostgreSQL host-failover engine | External HA endpoint required |
| Redis primary election | External HA endpoint required |
| TURN/SFU group calling | Not included in v6 |
