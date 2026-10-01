# Localgram v7 Load Test

Tool: k6.

Scenario:

```text
100 → 500 → 1000 → 2500 → 5000 VUs
```

Do not jump straight to 5000.

Files:

```text
loadtest/k6/localgram.js
loadtest/k6/users.json
```

Run:

```bash
k6 run \
  -e BASE_URL=https://staging-localgram.company.local \
  -e TARGET_VUS=100 \
  loadtest/k6/localgram.js
```

Watch in Grafana:
- p95 request latency;
- HTTP errors;
- CPU/RAM;
- PostgreSQL connections;
- Redis;
- security/moderation queues;
- message throughput.

Use many dedicated test accounts. One account cannot represent 5000 real users and will intentionally hit anti-spam/rate limits.


## WebSocket concurrency test

Use the dedicated WebSocket scenario:

```bash
k6 run -e BASE_URL=https://staging.localgram.company.local -e TARGET_VUS=100 loadtest/k6/websocket.js
```

Repeat at:

```text
100
500
1000
2500
5000
```

Use `loadtest/.env.loadtest.example` **only** on isolated staging so authentication/anti-spam policy does not distort an infrastructure-capacity benchmark.

Do not use production employees for the test. Create dedicated load-test accounts/conversations and watch Redis/ASGI/LB connections in Grafana.
