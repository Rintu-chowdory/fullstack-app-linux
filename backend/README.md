# Backend (FastAPI)

## Env vars (required unless noted)

| Var | Meaning |
|-----|---------|
| `JWT_SECRET` | token signing secret (required) |
| `DB_PASSWORD` (+ `DB_HOST/PORT/NAME/USER`) | MariaDB connection, or full `DATABASE_URL` |
| `ADMIN_PASSWORD` | initial admin password; random one logged if unset on fresh DB |
| `UPLOAD_DIR` | uploads dir (default `./uploads`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | token lifetime (default 480) |
| `CORS_ORIGINS` | comma-separated allowed origins |
| `MAX_UPLOAD_BYTES` | photo limit (default 5 MB) |

## Run

```bash
pip install -r requirements.txt
export JWT_SECRET=... DB_PASSWORD=... ADMIN_PASSWORD=...
python -m alembic upgrade head
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
python -m pytest tests -q     # runs on SQLite, no DB needed
```
