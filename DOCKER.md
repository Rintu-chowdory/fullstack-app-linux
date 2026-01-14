# Docker Compose (development)

This file explains how to run the app stack locally with Docker Compose.

Start the stack (build images on first run):

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f backend
```

Stop the stack:

```bash
docker compose down
```

Notes:
- Backend: http://localhost:8000 (health: /healthz)
- Frontend: http://localhost:3000

You can customize credentials in `.env` or use `.env.example` as a template.

The stack includes:
- `db` (MariaDB) with initial schema from `db/schema.sql`
- `backend` (FastAPI / uvicorn) built from `backend/Dockerfile.dev`
- `frontend` (Node / Express) built from `frontend/Dockerfile.dev`
