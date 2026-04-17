from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select

from app.bitrix_mention import bitrix_im_display_name
from app.bitrix_notify import bitrix_im_message_add, bitrix_messaging_pair_for_chat
from app.database import db_session, get_db
from app.deps import require_admin, require_support_or_admin
from app.duty_notifications import (
    apply_notification_settings,
    dispatch_duty_notification,
    notification_settings_to_out,
    send_test_duty_notification,
    _get_or_create_notification_settings,
)
from app.duty_slots import SLOT_COUNT, slot_start_time_str
from app.models import DutyAssignment, User
from app.schemas import (
    DutiesBatchRequest,
    DutiesGenerateOut,
    DutiesGenerateRequest,
    DutiesOut,
    DutyNotificationSettingsOut,
    DutyNotificationSettingsUpdateRequest,
    DutyNotificationDispatchOut,
    DutyScheduleBitrixDispatchOut,
    DutySlotOut,
    DutyTestNotificationOut,
    UserOut,
)

router = APIRouter()


@router.get("/api/duties", response_model=DutiesOut)
def get_duties(
    date_: date = Query(..., alias="date"),
    db=Depends(get_db),
    current_user: User = Depends(require_support_or_admin),
) -> DutiesOut:
    assignments = db.execute(
        select(DutyAssignment, User)
        .join(User, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date == date_)
    ).all()
    by_slot: dict[int, User] = {slot: user for (assignment, user) in assignments for slot in [assignment.slot]}

    slots_out: list[DutySlotOut] = []
    for slot in range(0, SLOT_COUNT):
        user = by_slot.get(slot)
        slots_out.append(
            DutySlotOut(
                slot=slot,
                start_time=slot_start_time_str(slot),
                user=UserOut(
                    id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    role=user.role,
                    is_active_for_duties=bool(user.is_active_for_duties),
                    bitrix_user_id=None,
                )
                if user
                else None,
            )
        )
    return DutiesOut(date=date_, slots=slots_out)


@router.post("/api/duties/generate", response_model=DutiesGenerateOut)
def generate_duties(payload: DutiesGenerateRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> DutiesGenerateOut:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    support_users = db.execute(
        select(User)
        .where(User.role.in_(("support", "admin")), User.is_active_for_duties == True)  # noqa: E712
        .order_by(User.id)
    ).scalars().all()
    if not support_users:
        raise HTTPException(status_code=400, detail="No users active for duties (support or admin)")

    user_ids = [u.id for u in support_users]

    existing_in_range: dict[tuple[date, int], int] = {}
    existing_rows = db.execute(
        select(DutyAssignment).where(DutyAssignment.date >= payload.start_date, DutyAssignment.date <= payload.end_date)
    ).scalars().all()
    for row in existing_rows:
        existing_in_range[(row.date, row.slot)] = row.support_user_id

    counts = {uid: 0 for uid in user_ids}
    grouped = db.execute(
        select(DutyAssignment.support_user_id, func.count())
        .where(DutyAssignment.date < payload.start_date)
        .group_by(DutyAssignment.support_user_id)
    ).all()
    for uid, cnt in grouped:
        if uid in counts:
            counts[uid] = int(cnt)

    created = 0
    rng = random.SystemRandom()

    with db_session() as tx_db:
        if payload.overwrite:
            tx_db.execute(
                delete(DutyAssignment).where(
                    DutyAssignment.date >= payload.start_date,
                    DutyAssignment.date <= payload.end_date,
                )
            )
            tx_db.commit()

        for uid in user_ids:
            counts[uid] = int(
                tx_db.execute(
                    select(func.count())
                    .select_from(DutyAssignment)
                    .where(DutyAssignment.support_user_id == uid, DutyAssignment.date < payload.start_date)
                ).scalar_one()
            )

        for day_index in range((payload.end_date - payload.start_date).days + 1):
            current_day = payload.start_date + timedelta(days=day_index)
            for slot in range(0, SLOT_COUNT):
                key = (current_day, slot)
                if (not payload.overwrite) and key in existing_in_range:
                    chosen_uid = existing_in_range[key]
                    counts[chosen_uid] = counts.get(chosen_uid, 0) + 1
                    continue

                min_count = min(counts.values())
                candidates = [uid for uid, c in counts.items() if c == min_count]
                chosen_uid = rng.choice(candidates)

                tx_db.add(DutyAssignment(date=current_day, slot=slot, support_user_id=chosen_uid))
                counts[chosen_uid] = counts.get(chosen_uid, 0) + 1
                created += 1

        tx_db.commit()

    return DutiesGenerateOut(
        start_date=payload.start_date,
        end_date=payload.end_date,
        overwrite=payload.overwrite,
        created_assignments=created,
    )


@router.post("/api/duties/batch")
def duties_batch(payload: DutiesBatchRequest, current_user: User = Depends(require_admin), db=Depends(get_db)) -> dict:
    if not payload.assignments:
        raise HTTPException(status_code=400, detail="assignments must not be empty")

    slots_seen: set[int] = set()
    for a in payload.assignments:
        if a.slot in slots_seen:
            raise HTTPException(status_code=400, detail="Duplicate slot in assignments")
        slots_seen.add(a.slot)

    user_ids = [a.user_id for a in payload.assignments]
    support_users = db.execute(
        select(User).where(User.id.in_(user_ids), User.role.in_(("support", "admin")))
    ).scalars().all()
    support_by_id = {u.id: u for u in support_users}
    missing = [uid for uid in user_ids if uid not in support_by_id]
    if missing:
        raise HTTPException(status_code=400, detail=f"Some users are invalid: {missing[0]}")
    for uid in user_ids:
        u = support_by_id[uid]
        if not u.is_active_for_duties:
            raise HTTPException(
                status_code=400,
                detail="Cannot assign an employee who is inactive for duties",
            )

    created = 0
    updated = 0
    with db_session() as tx_db:
        for a in payload.assignments:
            existing = tx_db.execute(
                select(DutyAssignment).where(DutyAssignment.date == payload.date, DutyAssignment.slot == a.slot)
            ).scalar_one_or_none()
            if existing:
                existing.support_user_id = a.user_id
                updated += 1
            else:
                tx_db.add(DutyAssignment(date=payload.date, slot=a.slot, support_user_id=a.user_id))
                created += 1
        tx_db.commit()

    return {"date": payload.date, "created": created, "updated": updated}


@router.get("/api/admin/notifications/settings", response_model=DutyNotificationSettingsOut)
def admin_get_notification_settings(
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationSettingsOut:
    row = _get_or_create_notification_settings(db)
    return notification_settings_to_out(row)


@router.patch("/api/admin/notifications/settings", response_model=DutyNotificationSettingsOut)
def admin_update_notification_settings(
    payload: DutyNotificationSettingsUpdateRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationSettingsOut:
    row = _get_or_create_notification_settings(db)
    apply_notification_settings(db, row, payload)
    db.commit()
    db.refresh(row)
    return notification_settings_to_out(row)


@router.post("/api/admin/notifications/duty-upcoming/dispatch", response_model=DutyNotificationDispatchOut)
def admin_dispatch_upcoming_duty_notification(
    at: Optional[datetime] = Query(None, description="Необязательно: время для расчёта слота (ISO)"),
    mode: str = Query(
        "upcoming_2m",
        pattern="^(upcoming_2m|upcoming_5m|start)$",
        description="upcoming_2m (legacy), upcoming_5m, start",
    ),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode=mode, at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-upcoming/5m", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_5m_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode="upcoming_5m", at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-upcoming/start", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_start_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode="start", at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-test", response_model=DutyTestNotificationOut)
def admin_send_test_duty_notification(
    user_id: int = Query(..., ge=1, description="ID сотрудника (таблица Админ)"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyTestNotificationOut:
    return send_test_duty_notification(db, user_id=user_id)


@router.post("/api/admin/notifications/duty-schedule/bitrix", response_model=DutyScheduleBitrixDispatchOut)
def admin_send_duty_schedule_to_bitrix(
    date_: Optional[date] = Query(None, alias="date", description="Дата графика; по умолчанию сегодня"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyScheduleBitrixDispatchOut:
    target_date = date_ or date.today()
    try:
        pair = bitrix_messaging_pair_for_chat()
    except HTTPException:
        raise
    if pair is None:
        raise HTTPException(
            status_code=400,
            detail="Bitrix not configured (set BITRIX_INCOMING_WEBHOOK_URL and BITRIX_NOTIFY_DIALOG_ID)",
        )
    bx_url, bx_dialog = pair

    rows = db.execute(
        select(DutyAssignment, User)
        .join(User, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date == target_date)
    ).all()
    by_slot: dict[int, User] = {assignment.slot: u for assignment, u in rows}

    lines = [f"Дежурства на {target_date.isoformat()}:"]
    for slot in range(0, SLOT_COUNT):
        t = slot_start_time_str(slot)
        u = by_slot.get(slot)
        lines.append(f"{t} — {bitrix_im_display_name(u)}" if u else f"{t} — не назначено")
    message = "\n".join(lines)

    bitrix_im_message_add(bx_url, bx_dialog, message)
    return DutyScheduleBitrixDispatchOut(sent=True, date=target_date)
