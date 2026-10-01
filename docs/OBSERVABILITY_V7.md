# Localgram v7 Observability

## Built-in operational page

```text
/control/infrastructure/
```

Shows PostgreSQL, Redis, MinIO/S3, ClamAV, workers, queues, online users, message rate and last restore verification.

## Prometheus + Grafana on Windows/dev

`METRICS_TOKEN` in `.env` must match the content of:

```text
infrastructure/prometheus/metrics_token
```

Example PowerShell:

```powershell
$token = "replace-with-a-long-random-token"
(Get-Content .env -Raw) -replace '(?m)^METRICS_TOKEN=.*$', "METRICS_TOKEN=$token" | Set-Content .env -Encoding UTF8
Set-Content .\infrastructure\prometheus\metrics_token $token -Encoding ASCII

docker compose -f docker-compose.yml -f docker-compose.monitoring.dev.yml up -d --build
```

Open locally:

```text
Prometheus http://127.0.0.1:9090
Grafana    http://127.0.0.1:3000
```

Grafana credentials come from:

```env
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE_GRAFANA_PASSWORD
```

## Production Linux

```bash
TOKEN='replace-with-a-long-random-token'
sed -i "s/^METRICS_TOKEN=.*/METRICS_TOKEN=$TOKEN/" .env
printf '%s\n' "$TOKEN" > infrastructure/prometheus/metrics_token

docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.monitoring.yml \
  up -d --build
```

Production monitoring adds:
- Prometheus;
- Grafana;
- PostgreSQL exporter;
- Redis exporter;
- node-exporter;
- cAdvisor.

Grafana/Prometheus bind to `127.0.0.1` by default. Publish them only through your admin VPN/reverse proxy if remote access is needed.

## Zabbix

Copy:

```text
infrastructure/zabbix/userparameter_localgram.conf
```

to the Zabbix Agent 2 config include directory on the Localgram Linux host. The example assumes:

```text
/opt/localgram
```

Then restart agent2. Prefer one master item `localgram.status` and Zabbix dependent items using JSONPath. Individual keys are also included for simple setups.

Available keys include:

```text
localgram.db
localgram.redis
localgram.users.online
localgram.messages.hour
localgram.security.queue
localgram.moderation.queue
localgram.worker.security
localgram.worker.moderation
localgram.worker.scheduler
localgram.dlp.open
localgram.malware
```

Use triggers for worker=0, db=0, redis=0, growing queues and infected attachments.
