# Localgram v7 deployment

## Recommended production topology

```text
Corporate TLS LB / F5 / HAProxy
            |
         Nginx
       /       \
    web1       web2
       \       /
       PgBouncer
           |
      PostgreSQL

Redis
MinIO/S3
ClamAV
moderator
securityworker
scheduler
Prometheus
Grafana
Zabbix Agent 2
```

For host-level HA use `docker-compose.app-node.yml` on multiple application nodes and point them to external HA PostgreSQL, Redis and distributed S3/MinIO endpoints.

## Production startup

```bash
cd /opt/localgram
cp .env.production.example .env
nano .env
```

Set strong secrets and real hostnames. Then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
./scripts/doctor_linux.sh
```

## Monitoring

`METRICS_TOKEN` in `.env` must match:

```text
infrastructure/prometheus/metrics_token
```

Then:

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.monitoring.yml \
  up -d --build
```

Keep Grafana/Prometheus bound to localhost or publish them only through the admin network.

## Zabbix

See `docs/OBSERVABILITY_V7.md`.

## Backups and restore validation

Backup:

```bash
./scripts/backup_linux.sh
```

Restore verification:

```bash
./scripts/restore_test_linux.sh
```

A production backup policy should also include PostgreSQL PITR/WAL archive and MinIO replication/versioning.

## GitLab CI/CD

See `docs/CI_CD_V7.md`.

## Load testing

See `docs/LOAD_TEST_V7.md`. Run on staging, gradually.

## Load balancer checks

```text
GET /healthz/
```

Do not expose DB, Redis, PgBouncer, ClamAV or MinIO internal API directly to end users.
