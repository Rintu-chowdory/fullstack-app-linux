# Database

MariaDB 10.11 (`dipti_portal`). Schema lives in **backend/alembic/versions/** as the
single source of truth - there is no separate schema.sql anymore.

Apply migrations (dev stack and CI do this automatically via the `migrate` service):

```bash
cd backend
DATABASE_URL="mysql+pymysql://dipti:PASSWORD@127.0.0.1:3306/dipti_portal?charset=utf8mb4" \
  python -m alembic upgrade head
```

Create a new migration after changing `backend/models.py`:

```bash
cd backend
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
```

Backups: `scripts/backup-db.sh`.
