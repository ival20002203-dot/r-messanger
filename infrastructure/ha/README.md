# Localgram v6 — true multi-node HA

`docker-compose.prod.yml` gives process-level redundancy (`web1` + `web2`) on one host.

For host-level HA use:

```text
Corporate LB / F5 / HAProxy
        |
   +----+----+
   |         |
App node A  App node B
   |         |
   +----+----+
        |
PostgreSQL HA endpoint
Redis HA endpoint
Distributed MinIO / S3
Shared private evidence storage
```

Each application node uses `docker-compose.app-node.yml`. The stable database endpoint may be a Patroni/HAProxy VIP, managed PostgreSQL, or your existing HA database platform. Localgram never attempts to elect a database primary itself.

Recommended environment on each node:

```env
DEBUG=0
ALLOWED_HOSTS=localgram.company.local
CSRF_TRUSTED_ORIGINS=https://localgram.company.local

POSTGRES_HA_HOST=10.0.0.50
POSTGRES_HA_PORT=5432
POSTGRES_DB=localgram
POSTGRES_USER=localgram
POSTGRES_PASSWORD=...

REDIS_URL=redis://10.0.0.60:6379/0

USE_S3_STORAGE=1
MINIO_ENDPOINT=https://s3-internal.company.local
MINIO_PUBLIC_ENDPOINT=https://files.localgram.company.local
MINIO_BUCKET=localgram-media
MINIO_ROOT_USER=...
MINIO_ROOT_PASSWORD=...

PRIVATE_MEDIA_HOST_PATH=/mnt/localgram-private
APP_NODE_PORT=8080
```

`PRIVATE_MEDIA_HOST_PATH` must point to the same NFS/SMB/CephFS data on all app nodes.

Run migrations once per release from one node, then start all nodes. Configure the corporate load balancer to health-check `/healthz/` on port 8080.
