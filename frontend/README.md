# Frontend (Express + EJS)

Server-rendered portal. Talks to the FastAPI backend via `BACKEND_API_BASE_URL`.
Sessions are stored in MariaDB (`express-mysql-session`) so both app nodes share
login state - the load balancer can route any request to either node.

## Env vars

| Var | Meaning |
|-----|---------|
| `SESSION_SECRET` | required - refuses to start without it |
| `BACKEND_API_BASE_URL` | backend URL (default `http://127.0.0.1:8000`) |
| `DB_*` | MariaDB for the session store |
| `COOKIE_SECURE` | `1` behind HTTPS |
| `TRUST_PROXY` | `1` behind HAProxy (trust X-Forwarded-*) |
| `SESSION_STORE=off` | dev-only memory fallback |

## Health

`GET /healthz` returns 200 only when the backend answers `/readyz` - HAProxy
removes an app node from rotation if either process is down.

## Run

```bash
npm ci
SESSION_SECRET=... BACKEND_API_BASE_URL=http://127.0.0.1:8000 DB_PASSWORD=... node src/server.js
```
