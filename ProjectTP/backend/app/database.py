from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.config import settings

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

engine = None
SessionLocal = None  # type: ignore


def get_database_url() -> str:
    """SQLAlchemy URL для PostgreSQL (обязательная переменная окружения DATABASE_URL)."""
    raw = (settings.DATABASE_URL or "").strip()
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is required (PostgreSQL), e.g. postgresql+psycopg://user:pass@127.0.0.1:5432/duty"
        )
    if not raw.startswith("postgresql"):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL (postgresql://, postgresql+psycopg://, or legacy +psycopg2)"
        )
    return raw


def run_migrations() -> None:
    """Apply Alembic migrations (PostgreSQL)."""
    from alembic import command
    from alembic.config import Config

    url = get_database_url()
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)

    pre = create_engine(url, pool_pre_ping=True)
    try:
        tables = set(inspect(pre).get_table_names())
        # БД до Alembic: таблицы уже есть, alembic_version нет — помечаем текущую ревизию без DDL.
        if "users" in tables and "alembic_version" not in tables:
            command.stamp(cfg, "head")
            return
    finally:
        pre.dispose()

    command.upgrade(cfg, "head")


def get_engine():
    global engine, SessionLocal
    if engine is not None:
        return engine

    url = get_database_url()
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine


@contextmanager
def db_session() -> Generator:
    if SessionLocal is None:
        get_engine()
    db = SessionLocal()  # type: ignore[misc]
    try:
        yield db
    finally:
        db.close()


def get_db():
    with db_session() as db:
        yield db
