"""Дублирующие эндпоинты dispatch с параметром strict_timing (см. также duties_live.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.deps import require_admin
from app.duty_notifications import dispatch_duty_notification
from app.models import User
from app.schemas import DutyNotificationDispatchOut

router = APIRouter()


@router.post("/api/admin/notifications/duty-upcoming/dispatch", response_model=DutyNotificationDispatchOut)
def admin_dispatch_upcoming_duty_notification(
    at: Optional[datetime] = Query(None, description="Необязательно: время для расчёта слота (ISO)"),
    mode: str = Query(
        "upcoming_2m",
        pattern="^(upcoming_2m|upcoming_5m|start)$",
        description="upcoming_2m (legacy), upcoming_5m, start",
    ),
    strict_timing: bool = Query(
        True,
        description="True — только ровно :55/:00 после сдвига; False — допуск ±3 мин к ближайшему часу (дрейф cron)",
    ),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(
        db, mode=mode, at=at, invoked_by_scheduler=False, strict_timing=strict_timing
    )


@router.post("/api/admin/notifications/duty-upcoming/5m", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_5m_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    strict_timing: bool = Query(
        True,
        description="См. /duty-upcoming/dispatch?strict_timing=",
    ),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(
        db, mode="upcoming_5m", at=at, invoked_by_scheduler=False, strict_timing=strict_timing
    )


@router.post("/api/admin/notifications/duty-upcoming/start", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_start_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    strict_timing: bool = Query(True, description="См. /duty-upcoming/dispatch?strict_timing="),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(
        db, mode="start", at=at, invoked_by_scheduler=False, strict_timing=strict_timing
    )
