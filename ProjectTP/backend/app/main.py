from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import db_session, run_migrations
from app.duty_notifications_runtime import apply_monkeypatches
from app.models import User
from app.security import hash_password

apply_monkeypatches()

from app.routers import register_routers

logger = logging.getLogger(__name__)

app = FastAPI(title="Support Duty & Reports API", redirect_slashes=False)

cors_origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def bootstrap_admin_if_needed(db) -> None:
    existing_users_count = db.execute(select(func.count()).select_from(User)).scalar_one()
    if existing_users_count and existing_users_count > 0:
        return

    if not settings.BOOTSTRAP_ADMIN_USERNAME or not settings.BOOTSTRAP_ADMIN_PASSWORD or not settings.BOOTSTRAP_ADMIN_FULLNAME:
        raise RuntimeError("Bootstrap admin env vars are required: BOOTSTRAP_ADMIN_USERNAME/PASSWORD/FULLNAME")

    admin = User(
        username=settings.BOOTSTRAP_ADMIN_USERNAME,
        full_name=settings.BOOTSTRAP_ADMIN_FULLNAME,
        role="admin",
        password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
    )
    db.add(admin)
    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    run_migrations()
    if not settings.SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET env var is required")

    with db_session() as db:
        bootstrap_admin_if_needed(db)
    try:
        from app.notification_scheduler import start_notification_scheduler

        start_notification_scheduler()
    except Exception:
        logger.exception("Встроенный планировщик уведомлений не запущен; API работает без авторассылки по расписанию")


@app.on_event("shutdown")
def on_shutdown() -> None:
    try:
        from app.notification_scheduler import stop_notification_scheduler

        stop_notification_scheduler()
    except Exception:
        logger.exception("Ошибка при остановке планировщика уведомлений")


app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie="session",
    same_site="lax",
    https_only=settings.SESSION_COOKIE_HTTPS_ONLY,
    max_age=settings.SESSION_MAX_AGE_SECONDS,
)

register_routers(app)
