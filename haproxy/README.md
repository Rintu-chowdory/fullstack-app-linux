# HAProxy load balancer

Two deployment modes:

## 1. Docker (single-machine HA lab)

Build with `Dockerfile.lb` (HAProxy + keepalived). See `docker-compose.prod.yml`
services `lb1` / `lb2` - keepalived runs inside the LB container with
`KEEPALIVED_ENABLED=1` and manages a virtual IP inside the docker network.

## 2. Bare metal / VMs (the 6-node lab)

Install HAProxy on lb1 and lb2:

```bash
sudo apt -y install haproxy
sudo cp haproxy.cfg /etc/haproxy/haproxy.cfg
```

The config uses environment variables (`APP1_HOST`, `APP2_HOST`, `STATS_USER`,
`STATS_PASSWORD`). Set them in `/etc/default/haproxy`:

```bash
sudo tee /etc/default/haproxy <<'ENV'
APP1_HOST=192.168.1.14
APP2_HOST=192.168.1.15
STATS_USER=admin
STATS_PASSWORD=change-me-stats
ENV
sudo systemctl enable --now haproxy
```

Point clients at the VIP `192.168.1.13` (see `keepalived/`). HAProxy checks each
app server with `GET /healthz` (the Express frontend reports `503` if its
FastAPI backend is unreachable, so a node is removed from rotation when either
process fails).

Stats page: `http://192.168.1.13:8404/stats`
