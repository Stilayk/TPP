"""Маршруты дежурств и уведомлений (рабочая копия: генерация вынесена в app.duty_generation)."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.bitrix_mention import bitrix_im_display_name
from app.bitrix_notify import bitrix_im_message_add, bitrix_messaging_pair_for_chat, bitrix_webhook_base_url
from app.database import db_session, get_db
from app.deps import require_admin, require_capability, require_capability_any, require_support_or_admin
from app.duty_copy import slot_updates_for_copy
from app.duty_export import build_duties_period_excel_bytes
from app.duty_generation import run_generation
from app.duty_notifications import (
    apply_notification_settings,
    apply_notification_templates,
    dispatch_duty_notification,
    notification_settings_to_out,
    notification_templates_to_out,
    send_test_duty_notification,
    _get_or_create_notification_settings,
)
from app.duty_slots import SLOT_COUNT, slot_start_time_str
from app.duty_tz import today_moscow
from app.models import DutyAssignment, User
from app.schemas import (
    DutiesBatchRequest,
    DutiesCopyRangeOut,
    DutiesCopyRangeRequest,
    DutiesGenerateOut,
    DutiesGenerateRequest,
    DutiesOut,
    DutyNotificationSettingsOut,
    DutyNotificationSettingsUpdateRequest,
    DutyNotificationTemplatesOut,
    DutyNotificationTemplatesUpdateRequest,
    DutyNotificationDispatchOut,
    DutyReplacementBitrixNotifyOut,
    DutyScheduleBitrixDispatchOut,
    DutySlotOut,
    DutyTestNotificationOut,
    UserOut,
)

router = APIRouter()

_MAX_DUTY_EXPORT_DAYS = 120


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
                    is_eligible_for_morning_duties=bool(user.is_eligible_for_morning_duties),
                    bitrix_user_id=None,
                )
                if user
                else None,
            )
        )
    return DutiesOut(date=date_, slots=slots_out)


@router.get("/api/duties/export-period")
def export_duties_period(
    start_date: date = Query(..., description="Начало периода (включительно)"),
    end_date: date = Query(..., description="Конец периода (включительно)"),
    current_user: User = Depends(require_capability("manage_duties")),
    db=Depends(get_db),
) -> Response:
    """Excel-таблица графика за период (те же слоты и ФИО, что в интерфейсе по данным БД)."""
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")
    span = (end_date - start_date).days + 1
    if span > _MAX_DUTY_EXPORT_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Period too long (max {_MAX_DUTY_EXPORT_DAYS} days)",
        )
    content = build_duties_period_excel_bytes(db, start_date=start_date, end_date=end_date)
    filename = f"duties_{start_date.isoformat()}_{end_date.isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/duties/generate", response_model=DutiesGenerateOut)
def generate_duties(
    payload: DutiesGenerateRequest, current_user: User = Depends(require_capability("manage_duties")), db=Depends(get_db)
) -> DutiesGenerateOut:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    existing_in_range: dict[tuple[date, int], int] = {}
    existing_rows = db.execute(
        select(DutyAssignment).where(DutyAssignment.date >= payload.start_date, DutyAssignment.date <= payload.end_date)
    ).scalars().all()
    for row in existing_rows:
        existing_in_range[(row.date, row.slot)] = row.support_user_id

    rng = random.SystemRandom()

    with db_session() as tx_db:
        created = run_generation(
            tx_db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            overwrite=payload.overwrite,
            existing_in_range=existing_in_range,
            rng=rng,
        )

    return DutiesGenerateOut(
        start_date=payload.start_date,
        end_date=payload.end_date,
        overwrite=payload.overwrite,
        created_assignments=created,
    )


@router.post("/api/duties/batch")
def duties_batch(
    payload: DutiesBatchRequest, current_user: User = Depends(require_capability("manage_duties")), db=Depends(get_db)
) -> dict:
    if not payload.assignments:
        raise HTTPException(status_code=400, detail="assignments must not be empty")

    slots_seen: set[int] = set()
    for a in payload.assignments:
        if a.slot in slots_seen:
            raise HTTPException(status_code=400, detail="Duplicate slot in assignments")
        slots_seen.add(a.slot)

    expected = set(range(SLOT_COUNT))
    if slots_seen != expected:
        raise HTTPException(
            status_code=400,
            detail=f"assignments must include each duty slot 0..{SLOT_COUNT - 1} exactly once",
        )

    user_ids = [a.user_id for a in payload.assignments if a.user_id is not None]
    _assert_assignees_for_duty_day(db, sorted(set(user_ids)))

    created = 0
    updated = 0
    deleted = 0
    with db_session() as tx_db:
        for a in payload.assignments:
            existing = tx_db.execute(
                select(DutyAssignment).where(DutyAssignment.date == payload.date, DutyAssignment.slot == a.slot)
            ).scalar_one_or_none()
            if a.user_id is None:
                if existing:
                    tx_db.delete(existing)
                    deleted += 1
                continue
            if existing:
                existing.support_user_id = a.user_id
                updated += 1
            else:
                tx_db.add(DutyAssignment(date=payload.date, slot=a.slot, support_user_id=a.user_id))
                created += 1
        tx_db.commit()

    return {"date": payload.date, "created": created, "updated": updated, "deleted": deleted}


def _assert_assignees_for_duty_day(db, user_ids: list[int]) -> None:
    if not user_ids:
        return
    support_users = (
        db.execute(select(User).where(User.id.in_(user_ids), User.role.in_(("support", "admin")))).scalars().all()
    )
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


@router.post("/api/duties/copy-range", response_model=DutiesCopyRangeOut)
def duties_copy_range(
    payload: DutiesCopyRangeRequest,
    current_user: User = Depends(require_capability("manage_duties")),
    db=Depends(get_db),
) -> DutiesCopyRangeOut:
    """Копирует назначения по дням: i-й день источника → i-й день цели (одинаковая длина диапазонов)."""
    if payload.source_end_date < payload.source_start_date:
        raise HTTPException(status_code=400, detail="source_end_date must be >= source_start_date")
    if payload.target_end_date < payload.target_start_date:
        raise HTTPException(status_code=400, detail="target_end_date must be >= target_start_date")

    n_src = (payload.source_end_date - payload.source_start_date).days + 1
    n_tgt = (payload.target_end_date - payload.target_start_date).days + 1
    if n_src != n_tgt:
        raise HTTPException(
            status_code=400,
            detail=f"Source and target ranges must contain the same number of days ({n_src} vs {n_tgt})",
        )

    created = 0
    updated = 0
    deleted = 0

    with db_session() as tx_db:
        for i in range(n_src):
            src_d = payload.source_start_date + timedelta(days=i)
            tgt_d = payload.target_start_date + timedelta(days=i)

            src_rows = tx_db.execute(select(DutyAssignment).where(DutyAssignment.date == src_d)).scalars().all()
            src_by_slot = {int(r.slot): int(r.support_user_id) for r in src_rows}

            tgt_rows = tx_db.execute(select(DutyAssignment).where(DutyAssignment.date == tgt_d)).scalars().all()
            tgt_by_slot = {int(r.slot): int(r.support_user_id) for r in tgt_rows}

            updates = slot_updates_for_copy(src_by_slot, tgt_by_slot, overwrite=payload.overwrite)

            day_uids = sorted({uid for _, uid in updates if uid is not None})
            _assert_assignees_for_duty_day(tx_db, day_uids)

            for slot, uid in updates:
                existing = tx_db.execute(
                    select(DutyAssignment).where(DutyAssignment.date == tgt_d, DutyAssignment.slot == slot)
                ).scalar_one_or_none()
                if uid is None:
                    if existing:
                        tx_db.delete(existing)
                        deleted += 1
                    continue
                if existing:
                    existing.support_user_id = uid
                    updated += 1
                else:
                    tx_db.add(DutyAssignment(date=tgt_d, slot=slot, support_user_id=uid))
                    created += 1
        tx_db.commit()

    return DutiesCopyRangeOut(days_copied=n_src, created=created, updated=updated, deleted=deleted)


@router.get("/api/admin/notifications/settings", response_model=DutyNotificationSettingsOut)
def admin_get_notification_settings(
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationSettingsOut:
    row = _get_or_create_notification_settings(db)
    return notification_settings_to_out(row)


@router.patch("/api/admin/notifications/settings", response_model=DutyNotificationSettingsOut)
def admin_update_notification_settings(
    payload: DutyNotificationSettingsUpdateRequest,
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationSettingsOut:
    row = _get_or_create_notification_settings(db)
    apply_notification_settings(db, row, payload)
    db.commit()
    db.refresh(row)
    return notification_settings_to_out(row)


@router.get("/api/admin/notifications/templates", response_model=DutyNotificationTemplatesOut)
def admin_get_notification_templates(
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationTemplatesOut:
    row = _get_or_create_notification_settings(db)
    return notification_templates_to_out(row)


@router.patch("/api/admin/notifications/templates", response_model=DutyNotificationTemplatesOut)
def admin_update_notification_templates(
    payload: DutyNotificationTemplatesUpdateRequest,
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationTemplatesOut:
    row = _get_or_create_notification_settings(db)
    apply_notification_templates(db, row, payload)
    db.commit()
    db.refresh(row)
    return notification_templates_to_out(row)


@router.post("/api/admin/notifications/duty-upcoming/dispatch", response_model=DutyNotificationDispatchOut)
def admin_dispatch_upcoming_duty_notification(
    at: Optional[datetime] = Query(None, description="Необязательно: время для расчёта слота (ISO)"),
    mode: str = Query(
        "upcoming_2m",
        pattern="^(upcoming_2m|upcoming_5m|start)$",
        description="upcoming_2m (legacy), upcoming_5m, start",
    ),
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode=mode, at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-upcoming/5m", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_5m_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode="upcoming_5m", at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-upcoming/start", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_start_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return dispatch_duty_notification(db, mode="start", at=at, invoked_by_scheduler=False)


@router.post("/api/admin/notifications/duty-test", response_model=DutyTestNotificationOut)
def admin_send_test_duty_notification(
    user_id: int = Query(..., ge=1, description="ID сотрудника (таблица Админ)"),
    current_user: User = Depends(require_capability("manage_notifications")),
    db=Depends(get_db),
) -> DutyTestNotificationOut:
    return send_test_duty_notification(db, user_id=user_id)


@router.post("/api/admin/notifications/duty-schedule/bitrix", response_model=DutyScheduleBitrixDispatchOut)
def admin_send_duty_schedule_to_bitrix(
    date_: Optional[date] = Query(None, alias="date", description="Дата графика; по умолчанию сегодня"),
    current_user: User = Depends(require_capability_any("manage_duties", "manage_notifications")),
    db=Depends(get_db),
) -> DutyScheduleBitrixDispatchOut:
    target_date = date_ or today_moscow()
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


@router.post("/api/me/duty-replacement-request/bitrix", response_model=DutyReplacementBitrixNotifyOut)
def me_notify_duty_replacement_bitrix(
    current_user: User = Depends(require_support_or_admin),
    db=Depends(get_db),
) -> DutyReplacementBitrixNotifyOut:
    """Личные сообщения в Битрикс всем пользователям с ролью admin и заполненным bitrix_user_id."""
    bx_url = bitrix_webhook_base_url()
    if not bx_url:
        raise HTTPException(
            status_code=400,
            detail="Bitrix not configured (set BITRIX_INCOMING_WEBHOOK_URL)",
        )
    admins = (
        db.execute(
            select(User).where(User.role == "admin", User.bitrix_user_id.is_not(None)),
        )
        .scalars()
        .all()
    )
    if not admins:
        raise HTTPException(
            status_code=400,
            detail="Ни у одного администратора не указан Bitrix ID (поле в карточке сотрудника в админке).",
        )
    who = bitrix_im_display_name(current_user)
    message = f"Запрос замены дежурства: сотрудника {who} необходимо заменить."
    for admin_user in admins:
        bitrix_im_message_add(bx_url, str(int(admin_user.bitrix_user_id)), message)
    return DutyReplacementBitrixNotifyOut(sent=True, recipients_bitrix=len(admins))
