"""Разрешение слота дежурства для уведомлений (строгий и допускающий дрейф cron)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.duty_slots import duty_slot_for_dt

RELAXED_SLOT_TOLERANCE = timedelta(minutes=3)


def _round_to_nearest_hour(dt: datetime) -> datetime:
    """Округление к ближайшему :00 (половина часа вверх при ровно :30)."""
    base = dt.replace(second=0, microsecond=0)
    if base.minute < 30:
        return base.replace(minute=0)
    if base.minute > 30:
        return base.replace(minute=0) + timedelta(hours=1)
    return base.replace(minute=0) + timedelta(hours=1)


def resolve_notification_slot(
    *,
    at: datetime | None,
    offset_minutes: int,
    strict_timing: bool = True,
) -> tuple[date, int, str] | tuple[None, None, str]:
    """
    strict_timing=True: после сдвига offset секунды и микросекунды должны быть 0, минуты — 00.
    strict_timing=False: якорь (at+offset) снапится к ближайшему часу в пределах RELAXED_SLOT_TOLERANCE.
    """
    anchor = (at or datetime.now()) + timedelta(minutes=offset_minutes)
    if strict_timing:
        target_dt = anchor
        # Как раньше в duties: достаточно ровно :00 минут после сдвига (cron APScheduler шлёт с секундой 0).
        if target_dt.minute != 0:
            return None, None, anchor.isoformat()
    else:
        snapped = _round_to_nearest_hour(anchor)
        if abs((anchor - snapped).total_seconds()) > RELAXED_SLOT_TOLERANCE.total_seconds():
            return None, None, anchor.isoformat()
        target_dt = snapped
    duty_date, duty_slot = duty_slot_for_dt(target_dt)
    if duty_date is None or duty_slot is None:
        return None, None, target_dt.isoformat()
    return duty_date, duty_slot, target_dt.isoformat()
