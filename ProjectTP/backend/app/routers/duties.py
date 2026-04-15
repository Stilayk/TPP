from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from app.bitrix_mention import bitrix_im_display_name
from app.config import settings
from app.database import db_session, get_db
from app.deps import require_admin, require_support_or_admin
from app.duty_slots import SLOT_COUNT, duty_slot_for_dt, slot_start_time_str
from app.models import DutyAssignment, DutyNotificationSettings, User
from app.schemas import (
    DutiesBatchRequest,
    DutiesGenerateOut,
    DutiesGenerateRequest,
    DutiesOut,
    DutyNotificationSettingsOut,
    DutyNotificationSettingsUpdateRequest,
    DutyNotificationDispatchOut,
    DutyNotificationMethodSettings,
    DutyScheduleBitrixDispatchOut,
    DutySlotOut,
    UserOut,
)

router = APIRouter()


def _bitrix_messaging_pair() -> tuple[str, str] | None:
    bx_url = (settings.BITRIX_INCOMING_WEBHOOK_URL or "").strip()
    bx_dialog = (settings.BITRIX_NOTIFY_DIALOG_ID or "").strip()
    has_bx_url = bool(bx_url)
    has_bx_dialog = bool(bx_dialog)
    if has_bx_url != has_bx_dialog:
        raise HTTPException(
            status_code=400,
            detail="Bitrix: set both BITRIX_INCOMING_WEBHOOK_URL and BITRIX_NOTIFY_DIALOG_ID, or leave both empty",
        )
    if has_bx_url and has_bx_dialog:
        return bx_url, bx_dialog
    return None


def _bitrix_webhook_base_url() -> str | None:
    bx_url = (settings.BITRIX_INCOMING_WEBHOOK_URL or "").strip()
    return bx_url or None


def _bitrix_im_message_add(base_url: str, dialog_id: str, message: str) -> None:
    base = base_url.rstrip("/") + "/"
    url = f"{base}im.message.add.json"
    body = json.dumps({"DIALOG_ID": dialog_id, "MESSAGE": message}).encode("utf-8")
    req = UrlRequest(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=settings.BITRIX_WEBHOOK_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        raw_err = e.read().decode("utf-8", errors="replace")
        detail = f"bitrix webhook HTTP {e.code}"
        try:
            err_data = json.loads(raw_err)
            if isinstance(err_data, dict) and err_data.get("error"):
                bd = err_data.get("error_description") or err_data.get("error")
                detail = f"bitrix: {bd} (HTTP {e.code})"
        except json.JSONDecodeError:
            if raw_err.strip():
                detail = f"{detail}: {raw_err.strip()[:400]}"
        raise HTTPException(status_code=502, detail=detail) from e
    except URLError as e:
        raise HTTPException(status_code=502, detail="bitrix webhook unreachable") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="bitrix: invalid JSON response")
    if isinstance(data, dict) and data.get("error"):
        desc = data.get("error_description") or data.get("error")
        raise HTTPException(status_code=502, detail=f"bitrix: {desc}")


def _resolve_notification_slot(
    *,
    at: datetime | None,
    offset_minutes: int,
) -> tuple[date, int, str] | tuple[None, None, str]:
    target_dt = (at or datetime.now()) + timedelta(minutes=offset_minutes)
    # Триггеры должны срабатывать в минуту старта слота (в том числе "за 5 минут" -> ровно HH:55).
    if target_dt.minute != 0:
        return None, None, target_dt.isoformat()
    duty_date, duty_slot = duty_slot_for_dt(target_dt)
    if duty_date is None or duty_slot is None:
        return None, None, target_dt.isoformat()
    return duty_date, duty_slot, target_dt.isoformat()


def _get_or_create_notification_settings(db) -> DutyNotificationSettings:
    row = db.get(DutyNotificationSettings, 1)
    if row:
        return row
    row = DutyNotificationSettings(id=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _notification_settings_out(row: DutyNotificationSettings) -> DutyNotificationSettingsOut:
    return DutyNotificationSettingsOut(
        selected_method=row.selected_method,
        cron=DutyNotificationMethodSettings(
            enabled_upcoming_5m=bool(row.cron_enabled_upcoming_5m),
            enabled_start=bool(row.cron_enabled_start),
            enabled_chat_on_start=bool(row.cron_enabled_chat_on_start),
        ),
        n8n=DutyNotificationMethodSettings(
            enabled_upcoming_5m=bool(row.n8n_enabled_upcoming_5m),
            enabled_start=bool(row.n8n_enabled_start),
            enabled_chat_on_start=bool(row.n8n_enabled_chat_on_start),
        ),
    )


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
    return _notification_settings_out(row)


@router.patch("/api/admin/notifications/settings", response_model=DutyNotificationSettingsOut)
def admin_update_notification_settings(
    payload: DutyNotificationSettingsUpdateRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationSettingsOut:
    row = _get_or_create_notification_settings(db)
    row.selected_method = payload.selected_method

    row.cron_enabled_upcoming_5m = payload.cron.enabled_upcoming_5m
    row.cron_enabled_start = payload.cron.enabled_start
    row.cron_enabled_chat_on_start = payload.cron.enabled_chat_on_start

    row.n8n_enabled_upcoming_5m = payload.n8n.enabled_upcoming_5m
    row.n8n_enabled_start = payload.n8n.enabled_start
    row.n8n_enabled_chat_on_start = payload.n8n.enabled_chat_on_start

    db.add(row)
    db.commit()
    db.refresh(row)
    return _notification_settings_out(row)


@router.post("/api/admin/notifications/duty-upcoming/dispatch", response_model=DutyNotificationDispatchOut)
def admin_dispatch_upcoming_duty_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    mode: str = Query(
        "upcoming_2m",
        pattern="^(upcoming_2m|upcoming_5m|start)$",
        description="upcoming_2m (legacy), upcoming_5m, start",
    ),
    source: str = Query(
        "cron",
        pattern="^(cron|n8n)$",
        description="Способ запуска уведомления (cron или n8n)",
    ),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    mode_to_offset = {
        "upcoming_2m": 2,
        "upcoming_5m": 5,
        "start": 0,
    }
    duty_date, duty_slot, target_iso = _resolve_notification_slot(
        at=at,
        offset_minutes=mode_to_offset[mode],
    )
    if duty_date is None or duty_slot is None:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"No duty slot at trigger moment ({target_iso})",
            event=mode,
            date=(at or datetime.now()).date(),
            slot=0,
            start_time="",
        )

    row = db.execute(
        select(DutyAssignment, User)
        .join(User, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date == duty_date, DutyAssignment.slot == duty_slot)
    ).first()
    if not row:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="No assigned employee for upcoming slot",
            event=mode,
            date=duty_date,
            slot=duty_slot,
            start_time=slot_start_time_str(duty_slot),
        )

    assignment, user = row
    start_time = slot_start_time_str(assignment.slot)
    settings_row = _get_or_create_notification_settings(db)
    if source != settings_row.selected_method:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"Notification source '{source}' is disabled; active source is '{settings_row.selected_method}'",
            event=mode,
            date=assignment.date,
            slot=assignment.slot,
            start_time=start_time,
            employee_id=user.id,
            employee_name=user.full_name,
            employee_bitrix_user_id=user.bitrix_user_id,
            n8n_sent=False,
            bitrix_personal_sent=False,
            bitrix_chat_sent=False,
        )

    if source == "cron":
        enabled_upcoming_5m = bool(settings_row.cron_enabled_upcoming_5m)
        enabled_start = bool(settings_row.cron_enabled_start)
        enabled_chat_on_start = bool(settings_row.cron_enabled_chat_on_start)
    else:
        enabled_upcoming_5m = bool(settings_row.n8n_enabled_upcoming_5m)
        enabled_start = bool(settings_row.n8n_enabled_start)
        enabled_chat_on_start = bool(settings_row.n8n_enabled_chat_on_start)

    if mode == "upcoming_5m" and not enabled_upcoming_5m:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"{source}: upcoming_5m notifications are disabled in admin settings",
            event=mode,
            date=assignment.date,
            slot=assignment.slot,
            start_time=start_time,
            employee_id=user.id,
            employee_name=user.full_name,
            employee_bitrix_user_id=user.bitrix_user_id,
            n8n_sent=False,
            bitrix_personal_sent=False,
            bitrix_chat_sent=False,
        )
    if mode == "start" and not enabled_start:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"{source}: start notifications are disabled in admin settings",
            event=mode,
            date=assignment.date,
            slot=assignment.slot,
            start_time=start_time,
            employee_id=user.id,
            employee_name=user.full_name,
            employee_bitrix_user_id=user.bitrix_user_id,
            n8n_sent=False,
            bitrix_personal_sent=False,
            bitrix_chat_sent=False,
        )
    payload = {
        "event": mode,
        "date": assignment.date.isoformat(),
        "slot": int(assignment.slot),
        "start_time": start_time,
        "employee": {
            "id": int(user.id),
            "full_name": user.full_name,
            "username": user.username,
            "bitrix_user_id": int(user.bitrix_user_id) if user.bitrix_user_id is not None else None,
        },
    }
    if mode == "upcoming_2m":
        personal_message = (
            f"Через 2 минуты дежурство: {user.full_name}, слот {start_time}, дата {assignment.date.isoformat()}."
        )
        chat_message = (
            f"Через 2 минуты дежурство: {bitrix_im_display_name(user)}, слот {start_time}, дата {assignment.date.isoformat()}."
        )
        need_personal = False
        need_chat = True
    elif mode == "upcoming_5m":
        personal_message = (
            f"Через 5 минут начинается ваше дежурство: {start_time}, дата {assignment.date.isoformat()}."
        )
        chat_message = ""
        need_personal = True
        need_chat = False
    else:  # start
        personal_message = f"Ваше дежурство началось: {start_time}, дата {assignment.date.isoformat()}."
        chat_message = (
            f"В дежурство вступил(а): {bitrix_im_display_name(user)}, слот {start_time}, дата {assignment.date.isoformat()}."
        )
        need_personal = True
        need_chat = enabled_chat_on_start

    n8n_configured = bool(settings.N8N_WEBHOOK_URL and settings.N8N_WEBHOOK_URL.strip())
    bitrix_url = _bitrix_webhook_base_url()
    bitrix_pair = _bitrix_messaging_pair() if need_chat else None

    if not n8n_configured and not bitrix_url and not bitrix_pair:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="No notification channels configured (N8N_WEBHOOK_URL and/or Bitrix env vars)",
            event=mode,
            date=assignment.date,
            slot=assignment.slot,
            start_time=start_time,
            employee_id=user.id,
            employee_name=user.full_name,
            employee_bitrix_user_id=user.bitrix_user_id,
            n8n_sent=None,
            bitrix_personal_sent=None,
            bitrix_chat_sent=None,
        )

    n8n_sent: bool | None = None
    if n8n_configured:
        req = UrlRequest(
            settings.N8N_WEBHOOK_URL.strip(),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=settings.N8N_WEBHOOK_TIMEOUT_SEC):
                pass
        except HTTPError as e:
            raise HTTPException(status_code=502, detail=f"n8n webhook error: {e.code}") from e
        except URLError as e:
            raise HTTPException(status_code=502, detail="n8n webhook unavailable") from e
        n8n_sent = True

    issues: list[str] = []

    bitrix_personal_sent: bool | None = None
    if need_personal:
        if not bitrix_url:
            issues.append("Bitrix webhook URL is not configured")
            bitrix_personal_sent = False
        elif user.bitrix_user_id is None:
            issues.append("Employee has no bitrix_user_id for personal notification")
            bitrix_personal_sent = False
        else:
            _bitrix_im_message_add(bitrix_url, str(user.bitrix_user_id), personal_message)
            bitrix_personal_sent = True

    bitrix_chat_sent: bool | None = None
    if need_chat:
        if bitrix_pair is None:
            issues.append("Bitrix chat dialog is not configured")
            bitrix_chat_sent = False
        else:
            bx_url, bx_dialog = bitrix_pair
            _bitrix_im_message_add(bx_url, bx_dialog, chat_message)
            bitrix_chat_sent = True

    sent_any = bool(n8n_sent or bitrix_personal_sent or bitrix_chat_sent)

    return DutyNotificationDispatchOut(
        sent=sent_any,
        reason="; ".join(issues) if issues else None,
        event=mode,
        date=assignment.date,
        slot=assignment.slot,
        start_time=start_time,
        employee_id=user.id,
        employee_name=user.full_name,
        employee_bitrix_user_id=user.bitrix_user_id,
        n8n_sent=n8n_sent,
        bitrix_personal_sent=bitrix_personal_sent,
        bitrix_chat_sent=bitrix_chat_sent,
    )


@router.post("/api/admin/notifications/duty-upcoming/5m", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_5m_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    source: str = Query("cron", pattern="^(cron|n8n)$"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return admin_dispatch_upcoming_duty_notification(
        at=at,
        mode="upcoming_5m",
        source=source,
        current_user=current_user,
        db=db,
    )


@router.post("/api/admin/notifications/duty-upcoming/start", response_model=DutyNotificationDispatchOut)
def admin_dispatch_duty_start_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    source: str = Query("cron", pattern="^(cron|n8n)$"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    return admin_dispatch_upcoming_duty_notification(
        at=at,
        mode="start",
        source=source,
        current_user=current_user,
        db=db,
    )


@router.post("/api/admin/notifications/duty-schedule/bitrix", response_model=DutyScheduleBitrixDispatchOut)
def admin_send_duty_schedule_to_bitrix(
    date_: Optional[date] = Query(None, alias="date", description="Дата графика; по умолчанию сегодня"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyScheduleBitrixDispatchOut:
    target_date = date_ or date.today()
    pair = _bitrix_messaging_pair()
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

    _bitrix_im_message_add(bx_url, bx_dialog, message)
    return DutyScheduleBitrixDispatchOut(sent=True, date=target_date)
