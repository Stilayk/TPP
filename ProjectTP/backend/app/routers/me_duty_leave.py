from __future__ import annotations

from fastapi import APIRouter, Depends

from app.database import get_db
from app.deps import get_current_user
from app.duty_leave_ops import (
    cancel_leave_dates_from_today,
    list_leave_dates_from_today,
    remove_today_leave_if_present,
    replace_leave_dates_from_today,
)
from app.models import User
from app.schemas import DutyLeaveDatesCancelOut, DutyLeaveDatesOut, DutyLeaveDatesPutRequest

router = APIRouter()


@router.get("/api/me/duty-leave-dates", response_model=DutyLeaveDatesOut)
def me_list_duty_leave_dates(current_user: User = Depends(get_current_user), db=Depends(get_db)) -> DutyLeaveDatesOut:
    return DutyLeaveDatesOut(dates=list_leave_dates_from_today(db, user_id=current_user.id))


@router.put("/api/me/duty-leave-dates", response_model=DutyLeaveDatesOut)
def me_put_duty_leave_dates(
    payload: DutyLeaveDatesPutRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutyLeaveDatesOut:
    replace_leave_dates_from_today(db, user=current_user, dates=list(payload.dates))
    return DutyLeaveDatesOut(dates=list_leave_dates_from_today(db, user_id=current_user.id))


@router.delete("/api/me/duty-leave-dates", response_model=DutyLeaveDatesCancelOut)
def me_delete_duty_leave_dates_future(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutyLeaveDatesCancelOut:
    n = cancel_leave_dates_from_today(db, user=current_user)
    return DutyLeaveDatesCancelOut(ok=True, removed=n)


@router.post("/api/me/duty-leave-dates/resume-today", response_model=DutyLeaveDatesOut)
def me_resume_duty_leave_today(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> DutyLeaveDatesOut:
    remove_today_leave_if_present(db, user=current_user)
    return DutyLeaveDatesOut(dates=list_leave_dates_from_today(db, user_id=current_user.id))
