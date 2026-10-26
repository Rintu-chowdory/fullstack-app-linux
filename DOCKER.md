# Docker

## Dev stack (single app pair)

```bash
cp .env.example .env    # set JWT_SECRET, SESSION_SECRET, ADMIN_PASSWORD, DB_PASSWORD
docker compose up --build -d
```

The `migrate` service runs `alembic upgrade head` once; the backend waits for
it (`service_completed_successfully`).

## HA lab (single machine, full topology)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

2 HAProxy/Keepalived LBs with VIP 172.28.0.13, two app pairs, MariaDB, shared
uploads volume. Host ports: lb1 8081, lb2 8082, stats 8404.

## Images

- `backend/Dockerfile` - python:3.12-slim, non-root, healthchecked
- `frontend/Dockerfile` - node:20-alpine, non-root, healthchecked
- `haproxy/Dockerfile.lb` - haproxy:2.9-alpine + keepalived

Keepalived needs `cap_add: [NET_ADMIN, NET_RAW]` (set in the compose file).
