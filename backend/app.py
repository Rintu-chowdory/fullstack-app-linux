import io
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import jwt
from database import SessionLocal
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from models import Student, StudentSubmission, User
from passlib.hash import bcrypt
from PIL import Image
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("dipti")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# ---------------------------------------------------------------- config
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Add it to your environment or .env "
        "(e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`)."
    )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "uploads"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_LOGIN_ATTEMPTS_PER_MIN = int(os.getenv("MAX_LOGIN_ATTEMPTS_PER_MIN", "10"))

os.makedirs(os.path.join(UPLOAD_DIR, "students"), exist_ok=True)

auth_scheme = HTTPBearer(auto_error=False)

app = FastAPI(title="DIPTI Backend API v3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------------------------------------------------------------- helpers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_login_attempts: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str, per_minute: int = MAX_LOGIN_ATTEMPTS_PER_MIN):
    """Tiny in-memory sliding-window limiter. Enough for a lab; the LB or an
    external WAF should do real rate limiting in production."""
    now = time.monotonic()
    attempts = _login_attempts[key]
    while attempts and now - attempts[0] > 60:
        attempts.popleft()
    if len(attempts) >= per_minute:
        raise HTTPException(status_code=429, detail="Too many attempts, try again in a minute")
    attempts.append(now)


def make_token(kind: str, subject: str, extra: dict | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, kind: str) -> dict:
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if decoded.get("kind") != kind:
        raise HTTPException(status_code=401, detail="Invalid token")
    return decoded


def require_admin(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing auth")
    return decode_token(creds.credentials, "admin")


def require_student(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing auth")
    return decode_token(creds.credentials, "student")


def ensure_admin():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "")
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(username=username).first()
        if existing:
            return
        if not password:
            password = secrets.token_urlsafe(16)
            log.warning("ADMIN_PASSWORD not set - generated one-time password for '%s': %s",
                        username, password)
        db.add(User(username=username, password_hash=bcrypt.hash(password), role="admin"))
        db.commit()
    finally:
        db.close()


ensure_admin()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------- schemas
class LoginIn(BaseModel):
    username: str
    password: str


class StudentIn(BaseModel):
    name: str
    institute: str
    batch: str
    course_name: str
    module: str
    email: EmailStr


class StudentLoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    token: str


# ---------------------------------------------------------------- health
@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "dipti-backend"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


# ---------------------------------------------------------------- admin auth
@app.post("/api/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(f"admin:{request.client.host if request.client else 'unknown'}")
    user = db.query(User).filter_by(username=payload.username).first()
    if not user or not bcrypt.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token("admin", user.username, {"role": user.role})}


# ---------------------------------------------------------------- admin: submissions & students
@app.post("/api/students")
def create_student(payload: StudentIn, db: Session = Depends(get_db), user=Depends(require_admin)):
    rec = StudentSubmission(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "status": "created"}


@app.get("/api/students")
def list_students(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    query = db.query(Student)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Student.name.like(like)) | (Student.email.like(like)) | (Student.batch.like(like))
        )
    total = query.count()
    rows = (
        query.order_by(Student.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "students": [
            {
                "id": s.id,
                "name": s.name,
                "institute": s.institute,
                "batch": s.batch,
                "course_name": s.course_name,
                "module": s.module,
                "email": s.email,
                "photo_url": f"/uploads/{s.profile_image_path}" if s.profile_image_path else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in rows
        ],
    }


# ---------------------------------------------------------------- student auth
@app.post("/api/students/register")
async def student_register(
    name: str = Form(...),
    institute: str = Form(...),
    batch: str = Form(...),
    course_name: str = Form(...),
    module: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    photo: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    check_rate_limit(f"register:{request.client.host if request else 'unknown'}", per_minute=20)
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    raw = await photo.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Photo exceeds 5 MB limit")
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    if db.query(Student).filter_by(email=str(email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # center-crop to square, resize, strip EXIF by re-encoding
    target = (256, 256)
    im_ratio = im.width / im.height
    tgt_ratio = target[0] / target[1]
    if im_ratio > tgt_ratio:
        new_height = im.height
        new_width = int(new_height * tgt_ratio)
    else:
        new_width = im.width
        new_height = int(new_width / tgt_ratio)
    left = (im.width - new_width) // 2
    top = (im.height - new_height) // 2
    im_cropped = im.crop((left, top, left + new_width, top + new_height)).resize(target)

    student = Student(
        name=name,
        institute=institute,
        batch=batch,
        course_name=course_name,
        module=module,
        email=str(email),
        password_hash=bcrypt.hash(password),
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    out_dir = os.path.join(UPLOAD_DIR, "students")
    os.makedirs(out_dir, exist_ok=True)
    img_path = os.path.join(out_dir, f"{student.id}.jpg")
    im_cropped.save(img_path, format="JPEG", quality=90)
    student.profile_image_path = f"students/{student.id}.jpg"
    db.commit()

    return {"id": student.id, "status": "registered"}


@app.post("/api/student/login", response_model=TokenOut)
def student_login(payload: StudentLoginIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(f"student:{request.client.host if request.client else 'unknown'}")
    s = db.query(Student).filter_by(email=str(payload.email)).first()
    if not s or not bcrypt.verify(payload.password, s.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": make_token("student", s.email, {"sid": s.id})}


@app.get("/api/student/me")
def student_me(auth=Depends(require_student), db: Session = Depends(get_db)):
    s = db.get(Student, auth["sid"])
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": s.id,
        "name": s.name,
        "email": s.email,
        "institute": s.institute,
        "batch": s.batch,
        "course_name": s.course_name,
        "module": s.module,
        "photo_url": f"/uploads/{s.profile_image_path}" if s.profile_image_path else None,
    }
