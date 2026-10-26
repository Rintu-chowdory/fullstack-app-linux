# Hosting (free tier)

`render.yaml` deploys the whole portal on Render's free tier:
backend (FastAPI), frontend (Express/EJS), free Postgres (expires 30 days
after creation - re-create and re-run migrations when it does).

The app supports Postgres via `DATABASE_URL` (SQLAlchemy + psycopg2). Free
tier caveat: services sleep after 15 min idle, so the first request is slow.

1. Push this repo to GitHub
2. Render Dashboard -> New -> Blueprint -> select the repo
3. Fill the `sync: false` env vars: `ADMIN_PASSWORD`, `CORS_ORIGINS`,
   `BACKEND_API_BASE_URL` (the dipti-backend service URL)
