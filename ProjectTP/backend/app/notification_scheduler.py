"""Встроенный планировщик: каждый час в :55 и :00 вызывает рассылку уведомлений о дежурствах.

Импорт APScheduler выполняется внутри start_notification_scheduler(), чтобы при проблеме с зависимостью
приложение всё равно поднималось (uvicorn + /api/health).
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import db_session
from app.duty_notifications import dispatch_duty_notification

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _tick_5m() -> None:
    try:
        with db_session() as db:
            out = dispatch_duty_notification(db, mode="upcoming_5m", at=None, invoked_by_scheduler=True)
            logger.info("duty notify upcoming_5m: sent=%s reason=%s slot=%s", out.sent, out.reason, out.slot)
    except Exception:
        logger.exception("duty notify upcoming_5m failed")


def _tick_start() -> None:
    try:
        with db_session() as db:
            out = dispatch_duty_notification(db, mode="start", at=None, invoked_by_scheduler=True)
            logger.info("duty notify start: sent=%s reason=%s slot=%s", out.sent, out.reason, out.slot)
    except Exception:
        logger.exception("duty notify start failed")


def start_notification_scheduler() -> None:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    global _scheduler
    if _scheduler is not None:
        return
    tz_name = (settings.TZ or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.warning("Invalid TZ %r, falling back to UTC", tz_name)
        tz = ZoneInfo("UTC")
    _scheduler = BackgroundScheduler(timezone=tz, daemon=True)
    _scheduler.add_job(
        _tick_5m,
        CronTrigger(minute=55, second=0, timezone=tz),
        id="duty_upcoming_5m",
        replace_existing=True,
    )
    _scheduler.add_job(
        _tick_start,
        CronTrigger(minute=0, second=0, timezone=tz),
        id="duty_start",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Notification scheduler started (TZ=%s)", tz_name)


def stop_notification_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Notification scheduler stopped")
