# Localgram v7 load test

Use an isolated staging environment. Do **not** point 5,000 VUs at production first.

1. Create many dedicated test users and conversations.
2. Set `LOGIN_EMAIL_2FA=0` **only on the isolated load-test environment**.
3. Increase rate-limit thresholds for the test if the goal is infrastructure capacity rather than abuse-policy validation.
4. Edit `loadtest/k6/users.json`.

Run 100 VUs:

```bash
k6 run -e BASE_URL=https://staging-localgram.company.local -e TARGET_VUS=100 loadtest/k6/localgram.js
```

Then step through 500 → 1000 → 2500 → 5000 while watching Grafana/PostgreSQL/Redis/MinIO/CPU/RAM.


## Capacity-policy environment

For infrastructure-capacity tests, use a dedicated staging `.env` derived from:

```text
loadtest/.env.loadtest.example
```

This deliberately raises abuse-policy limits and disables anti-spam only on the isolated load-test environment. Do not copy these values to production.

## WebSocket concurrency

WebSocket test:

```bash
k6 run \
  -e BASE_URL=https://staging-localgram.company.local \
  -e TARGET_VUS=100 \
  loadtest/k6/websocket.js
```

Then repeat:

```text
100 → 500 → 1000 → 2500 → 5000
```

For large runs, `users.json` should contain many dedicated accounts. It may optionally contain pre-issued test-only:

```json
{
  "email":"load001@texnopark.uz",
  "password":"...",
  "access_token":"...",
  "conversation_id":"..."
}
```

Pre-issued tokens avoid a login burst becoming the bottleneck when the purpose is measuring WebSocket capacity.

Watch:
- `localgram_ws_connected`;
- `localgram_ws_connect_ms`;
- ASGI CPU/RAM;
- Redis connections/memory;
- PostgreSQL connections;
- Nginx/LB active connections.

Run REST/message and WebSocket tests separately first; only combine them after each baseline is understood.
