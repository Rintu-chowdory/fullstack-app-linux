import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def normalize_database_url(url: str) -> str:
    """SQLAlchemy 2.x rejects the postgres:// scheme Render provides."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def build_database_url() -> str:
    """DATABASE_URL wins; otherwise assemble from DB_* parts."""
    url = normalize_database_url(os.getenv("DATABASE_URL", "").strip())
    if url:
        return url
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "dipti_portal")
    user = os.getenv("DB_USER", "dipti")
    password = os.getenv("DB_PASSWORD", "")
    if not password:
        raise RuntimeError("DB_PASSWORD or DATABASE_URL must be set")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


DATABASE_URL = build_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
