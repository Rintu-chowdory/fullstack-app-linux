# DIPTI Student Portal - HA Linux lab + fullstack app

A small but complete fullstack app (FastAPI + Express/EJS + MariaDB) built for
learning **high-availability Linux infrastructure**: HAProxy load balancing,
VRRP failover with Keepalived, NFS shared storage, and database-backed sessions
across app nodes.

Runs in three modes, small to large:

1. **Dev stack** - one machine, `docker compose up --build -d` (single app pair)
2. **Single-machine HA lab** - `docker-compose.prod.yml`: 2 load balancers with
   a keepalived VIP, 2 app pairs, 1 DB, simulated NFS - all on one host
3. **6-VM HA cluster** - the real thing on Ubuntu 24.04 VMs

## The application

- Students register with profile photo (center-cropped, EXIF-stripped) and log
  in to a profile page
- Admins log in, browse/search/paginate registered students, add manual entries
- Auth: JWT with expiry; frontend sessions live in MariaDB (shared by app1+app2)
- Migrations: Alembic (single source of truth for the schema)
- Tests: pytest API suite; CI runs lint + migrations + tests + a full-stack
  integration journey through the real compose stack

```
client ──> HAProxy (lb1 ─ VRRP VIP .13 ─ lb2)
              ├──> app1: Express/EJS :3000 ──> FastAPI :8000 ──┐
              └──> app2: Express/EJS :3000 ──> FastAPI :8000 ──┤
                                                            MariaDB :3306
              uploads: NFS share (app1 + app2 mount the same dir)
```

## Quick start (dev stack)

```bash
cp .env.example .env      # fill in real secrets
docker compose up --build -d
# frontend  http://localhost:3000   admin: $ADMIN_USERNAME/$ADMIN_PASSWORD
# api       http://localhost:8000/healthz
```

The `migrate` service applies Alembic migrations before the backend starts.

## Single-machine HA lab

Requires Linux + Docker (keepalived needs `NET_ADMIN`).

```bash
cp .env.example .env      # also set STATS_PASSWORD + VRRP_PASSWORD
docker compose -f docker-compose.prod.yml up --build -d
```

- App via HAProxy: http://localhost:8081 (lb1) / http://localhost:8082 (lb2)
- VIP inside the docker net: 172.28.0.13 (both LBs answer for it)
- HAProxy stats: http://localhost:8404/stats

**Failover drills** (watch the stats page while running them):

```bash
# app node failure: HAProxy drops the node, requests continue on app2
docker compose -f docker-compose.prod.yml stop app1-backend
curl -s http://localhost:8081/healthz

# load balancer failure: keepalived moves the VIP to lb2
docker compose -f docker-compose.prod.yml stop lb1
curl -s http://localhost:8082/healthz
```

## The 6-VM cluster (Ubuntu 24.04)

| Role        | Hostname | IP           | Key software                    |
|-------------|----------|--------------|---------------------------------|
| LB primary  | lb1      | 192.168.1.11 | HAProxy + Keepalived (MASTER 150)|
| LB backup   | lb2      | 192.168.1.12 | HAProxy + Keepalived (BACKUP 100)|
| Virtual IP  | -        | 192.168.1.13 | VRRP VIP clients connect to     |
| App server  | app1     | 192.168.1.14 | Node 20 frontend + FastAPI 3.12 |
| App server  | app2     | 192.168.1.15 | Node 20 frontend + FastAPI 3.12 |
| Database    | db1      | 192.168.1.16 | MariaDB 10.11                    |
| NFS storage | nfs1     | 192.168.1.17 | nfs-kernel-server                |

### 1. All hosts

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install curl git
sudo timedatectl set-timezone Asia/Dhaka   # or your zone
```

### 2. db1 - MariaDB

```bash
sudo apt -y install mariadb-server
sudo mysql_secure_installation
sudo mysql -e "CREATE DATABASE dipti_portal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'dipti'@'192.168.1.%' IDENTIFIED BY 'DB_PASSWORD';
GRANT ALL ON dipti_portal.* TO 'dipti'@'192.168.1.%'; FLUSH PRIVILEGES;"
# bind-address = 192.168.1.16 in /etc/mysql/mariadb.conf.d/50-server.cnf, restart
```

### 3. nfs1

```bash
sudo ./nfs/setup-nfs-server.sh
```

### 4. app1 + app2

```bash
sudo apt -y install python3.12 python3-pip nodejs npm   # or install via nodesource/deadsnakes
sudo ./nfs/mount-app-server.sh                         # shared uploads dir
# backend
cd backend && pip install -r requirements.txt
export DB_HOST=192.168.1.16 DB_PASSWORD=... JWT_SECRET=... ADMIN_PASSWORD=... UPLOAD_DIR=/opt/dipti/uploads
python -m alembic upgrade head        # once, on app1
uvicorn app:app --host 0.0.0.0 --port 8000
# frontend (separate shell / systemd unit)
cd frontend && npm ci
BACKEND_API_BASE_URL=http://127.0.0.1:8000 SESSION_SECRET=... DB_HOST=192.168.1.16 DB_PASSWORD=... node src/server.js
```

Write **systemd units** for uvicorn and node (`systemctl enable --now`), so
services survive reboots.

### 5. lb1 + lb2

```bash
sudo apt -y install haproxy keepalived
# lb1:
sudo cp haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg
sudo tee /etc/default/haproxy <<< "APP1_HOST=192.168.1.14 APP2_HOST=192.168.1.15 STATS_USER=admin STATS_PASSWORD=..."
sudo cp keepalived/keepalived-lb1.conf /etc/keepalived/keepalived.conf
# lb2: same haproxy.cfg + keepalived-lb2.conf
sudo systemctl enable --now haproxy keepalived
```

### 6. Verify the cluster

```bash
curl http://192.168.1.13:3000/ -I            # through the VIP
sudo ip addr show | grep 192.168.1.13        # which LB holds the VIP
sudo systemctl stop keepalived               # on lb1: VIP moves to lb2
```

## Security notes

- `JWT_SECRET` and `SESSION_SECRET` are mandatory (the services refuse to start
  without them)
- Admin password comes from `ADMIN_PASSWORD`; if unset on a fresh DB, a random
  one-time password is generated and logged
- CSRF tokens on every form; login endpoints rate-limited; helmet CSP; httpOnly
  session cookies (`COOKIE_SECURE=1` for HTTPS)
- Never disable firewalls in production - the lab uses `allow 80,443,3000,8000,3306`

## Operations

- Backups: `DB_PASSWORD=... ./scripts/backup-db.sh` (keeps last 30)
- Logs: `docker compose logs -f backend` / journald in the VM lab
- Migrations: see `db/README.md`

## Layout

```
backend/    FastAPI app, models, Alembic migrations, pytest suite
frontend/   Express + EJS server-rendered app (sessions in MariaDB)
haproxy/    LB config + Dockerfile.lb (HAProxy + keepalived image)
keepalived/ VRRP configs for lb1 (MASTER) / lb2 (BACKUP)
nfs/        NFS server + app-server mount scripts
scripts/    db backup script
db/         migration docs
.github/    CI: lint, migrations, pytest, compose integration journey
```
