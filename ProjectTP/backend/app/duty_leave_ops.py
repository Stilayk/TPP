"""Операции с днями без участия в автогенерации графика (duty_participation_leave)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.duty_tz import today_moscow
from app.models import DutyParticipationLeave, User

TECHNICAL_SCHEDULE_USERNAME = "user"
_MAX_DATES_PER_SAVE = 400


def assert_user_may_edit_leave_calendar(user: User) -> None:
    if user.role not in ("support", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if (user.username or "").strip().lower() == TECHNICAL_SCHEDULE_USERNAME:
        raise HTTPException(
            status_code=400,
            detail='Учётная запись с логином "user" закреплена за слотом 09:00; отгулы от генерации для неё не задаются.',
        )


def list_leave_dates_from_today(db, *, user_id: int) -> list[date]:
    t = today_moscow()
    rows = (
        db.execute(
            select(DutyParticipationLeave.leave_date)
            .where(DutyParticipationLeave.user_id == user_id, DutyParticipationLeave.leave_date >= t)
            .order_by(DutyParticipationLeave.leave_date)
        )
        .scalars()
        .all()
    )
    return list(rows)


def leave_dates_map_from_today(db, user_ids: list[int]) -> dict[int, list[date]]:
    if not user_ids:
        return {}
    t = today_moscow()
    rows = db.execute(
        select(DutyParticipationLeave.user_id, DutyParticipationLeave.leave_date)
        .where(DutyParticipationLeave.user_id.in_(user_ids), DutyParticipationLeave.leave_date >= t)
        .order_by(DutyParticipationLeave.user_id, DutyParticipationLeave.leave_date)
    ).all()
    m: dict[int, list[date]] = defaultdict(list)
    for uid, ld in rows:
        m[int(uid)].append(ld)
    return dict(m)


def replace_leave_dates_from_today(db, *, user: User, dates: list[date]) -> int:
    assert_user_may_edit_leave_calendar(user)
    t = today_moscow()
    uniq = sorted({d for d in dates if d >= t})
    if len(uniq) > _MAX_DATES_PER_SAVE:
        raise HTTPException(status_code=400, detail=f"Слишком много дат (максимум {_MAX_DATES_PER_SAVE})")
    db.execute(
        delete(DutyParticipationLeave).where(
            DutyParticipationLeave.user_id == user.id,
            DutyParticipationLeave.leave_date >= t,
        )
    )
    for d in uniq:
        db.add(DutyParticipationLeave(user_id=user.id, leave_date=d))
    db.commit()
    return len(uniq)


def cancel_leave_dates_from_today(db, *, user: User) -> int:
    assert_user_may_edit_leave_calendar(user)
    t = today_moscow()
    res = db.execute(
        delete(DutyParticipationLeave).where(
            DutyParticipationLeave.user_id == user.id,
            DutyParticipationLeave.leave_date >= t,
        )
    )
    db.commit()
    return int(res.rowcount or 0)


def remove_today_leave_if_present(db, *, user: User) -> bool:
    """Снять отсутствие только на сегодня (МСК); будущие отмеченные дни сохраняются."""
    assert_user_may_edit_leave_calendar(user)
    t = today_moscow()
    res = db.execute(
        delete(DutyParticipationLeave).where(
            DutyParticipationLeave.user_id == user.id,
            DutyParticipationLeave.leave_date == t,
        )
    )
    db.commit()
    return int(res.rowcount or 0) > 0


def user_ids_on_leave_for_day(db, *, day: date) -> set[int]:
    rows = db.execute(select(DutyParticipationLeave.user_id).where(DutyParticipationLeave.leave_date == day)).scalars().all()
    return {int(x) for x in rows}
