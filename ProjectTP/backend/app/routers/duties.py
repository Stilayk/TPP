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
from app.models import DutyAssignment, User
from app.schemas import (
    DutiesBatchRequest,
    DutiesGenerateOut,
    DutiesGenerateRequest,
    DutiesOut,
    DutyNotificationDispatchOut,
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


@router.post("/api/admin/notifications/duty-upcoming/dispatch", response_model=DutyNotificationDispatchOut)
def admin_dispatch_upcoming_duty_notification(
    at: Optional[datetime] = Query(None, description="Optional override time, ISO datetime"),
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
) -> DutyNotificationDispatchOut:
    target_dt = (at or datetime.now()) + timedelta(minutes=2)
    duty_date, duty_slot = duty_slot_for_dt(target_dt)
    if duty_date is None or duty_slot is None:
        raise HTTPException(status_code=400, detail="No duty slot in +2 minute window")

    row = db.execute(
        select(DutyAssignment, User)
        .join(User, DutyAssignment.support_user_id == User.id)
        .where(DutyAssignment.date == duty_date, DutyAssignment.slot == duty_slot)
    ).first()
    if not row:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="No assigned employee for upcoming slot",
            date=duty_date,
            slot=duty_slot,
            start_time=slot_start_time_str(duty_slot),
        )

    assignment, user = row
    start_time = slot_start_time_str(assignment.slot)
    payload = {
        "event": "duty_upcoming_2m",
        "date": assignment.date.isoformat(),
        "slot": int(assignment.slot),
        "start_time": start_time,
        "employee": {
            "id": int(user.id),
            "full_name": user.full_name,
            "username": user.username,
        },
    }
    human_message = (
        f"Через 2 минуты дежурство: {bitrix_im_display_name(user)}, слот {start_time}, дата {assignment.date.isoformat()}"
    )

    n8n_configured = bool(settings.N8N_WEBHOOK_URL and settings.N8N_WEBHOOK_URL.strip())
    bitrix_pair = _bitrix_messaging_pair()

    if not n8n_configured and bitrix_pair is None:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="No notification channels configured (N8N_WEBHOOK_URL and/or Bitrix env vars)",
            date=assignment.date,
            slot=assignment.slot,
            start_time=start_time,
            employee_id=user.id,
            employee_name=user.full_name,
            n8n_sent=None,
            bitrix_sent=None,
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

    bitrix_sent: bool | None = None
    if bitrix_pair is not None:
        bx_url, bx_dialog = bitrix_pair
        _bitrix_im_message_add(bx_url, bx_dialog, human_message)
        bitrix_sent = True

    return DutyNotificationDispatchOut(
        sent=True,
        date=assignment.date,
        slot=assignment.slot,
        start_time=start_time,
        employee_id=user.id,
        employee_name=user.full_name,
        n8n_sent=n8n_sent,
        bitrix_sent=bitrix_sent,
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
