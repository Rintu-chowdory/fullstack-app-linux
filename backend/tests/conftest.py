import io
import os
import tempfile
import uuid

os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test-secret-for-ci")
os.environ["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin-test-password")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="dipti-uploads-")
# per-test sqlite file DB
_DB = os.path.join(tempfile.mkdtemp(prefix="dipti-db-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import models  # noqa: F401  (register tables on Base)
from database import Base, engine
from fastapi.testclient import TestClient
from PIL import Image

Base.metadata.create_all(bind=engine)

from app import app

client = TestClient(app)


def admin_headers() -> dict:
    resp = client.post("/api/login", json={"username": "admin", "password": "admin-test-password"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def png_bytes(size: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=(200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def register_student(email: str | None = None, password: str = "password123") -> dict:
    data = {
        "name": "Test Student",
        "institute": "DIPTI",
        "batch": "B1",
        "course_name": "Linux HA",
        "module": "M1",
        "email": email or f"{uuid.uuid4().hex[:10]}@example.com",
        "password": password,
    }
    files = {"photo": ("photo.png", png_bytes(), "image/png")}
    return {"data": data, "files": files}
