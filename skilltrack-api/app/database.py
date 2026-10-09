import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# Connections per server process = pool_size + max_overflow. Keep (processes x that) under the database's limit.
# pool_pre_ping replaces connections that went stale while Neon's compute was suspended.
engine = create_engine(
    DATABASE_URL, pool_pre_ping=True,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "30")),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
