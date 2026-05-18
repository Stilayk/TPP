"""Логика рассылки уведомлений о дежурствах (Битрикс ЛС + общий чат, опционально n8n)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrllibRequest, urlopen

from app.bitrix_notify import (
    bitrix_im_message_add,
    bitrix_messaging_pair_for_chat,
    bitrix_webhook_base_url,
)
from app.bitrix_mention import bitrix_im_display_name
from app.config import settings
from app.duty_slots import duty_slot_for_dt, slot_start_time_str
from app.duty_tz import anchor_dispatch_at, today_moscow
from app.models import DutyAssignment, DutyNotificationSettings, User
from app.schemas import (
    DutyNotificationDispatchOut,
    DutyNotificationSettingsOut,
    DutyNotificationSettingsUpdateRequest,
    DutyNotificationTemplatesOut,
    DutyNotificationTemplatesUpdateRequest,
    DutyTestNotificationOut,
)


def _resolve_notification_slot(
    *,
    at: datetime | None,
    offset_minutes: int,
) -> tuple[date, int, str] | tuple[None, None, str]:
    target_dt = anchor_dispatch_at(at) + timedelta(minutes=offset_minutes)
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


def notification_settings_to_out(row: DutyNotificationSettings) -> DutyNotificationSettingsOut:
    return DutyNotificationSettingsOut(
        scheduler_enabled=bool(getattr(row, "scheduler_enabled", True)),
        enabled_upcoming_5m=bool(row.cron_enabled_upcoming_5m),
        enabled_start=bool(row.cron_enabled_start),
        enabled_chat_on_start=bool(row.cron_enabled_chat_on_start),
    )


def apply_notification_settings(
    db, row: DutyNotificationSettings, payload: DutyNotificationSettingsUpdateRequest
) -> None:
    """Сохраняет единый набор флагов в cron_* и дублирует в n8n_* (обратная совместимость)."""
    row.scheduler_enabled = payload.scheduler_enabled
    row.cron_enabled_upcoming_5m = payload.enabled_upcoming_5m
    row.cron_enabled_start = payload.enabled_start
    row.cron_enabled_chat_on_start = payload.enabled_chat_on_start
    row.n8n_enabled_upcoming_5m = payload.enabled_upcoming_5m
    row.n8n_enabled_start = payload.enabled_start
    row.n8n_enabled_chat_on_start = payload.enabled_chat_on_start
    db.add(row)


def notification_templates_to_out(row: DutyNotificationSettings) -> DutyNotificationTemplatesOut:
    return DutyNotificationTemplatesOut(
        upcoming_5m_template=row.upcoming_5m_template,
        start_personal_template=row.start_personal_template,
        start_chat_template=row.start_chat_template,
        test_with_slot_template=row.test_with_slot_template,
        test_without_slot_template=row.test_without_slot_template,
    )


def apply_notification_templates(
    db, row: DutyNotificationSettings, payload: DutyNotificationTemplatesUpdateRequest
) -> None:
    row.upcoming_5m_template = payload.upcoming_5m_template.strip()
    row.start_personal_template = payload.start_personal_template.strip()
    row.start_chat_template = payload.start_chat_template.strip()
    row.test_with_slot_template = payload.test_with_slot_template.strip()
    row.test_without_slot_template = payload.test_without_slot_template.strip()
    db.add(row)


def _render_notification_template(template: str, values: dict[str, str]) -> str:
    try:
        rendered = str(template).format(**values)
    except KeyError as e:
        key = str(e).strip("'")
        raise HTTPException(status_code=400, detail=f"Unknown template placeholder: {key}") from e
    return rendered.strip()


def dispatch_duty_notification(
    db,
    *,
    mode: str,
    at: Optional[datetime] = None,
    invoked_by_scheduler: bool = False,
) -> DutyNotificationDispatchOut:
    """
    mode: upcoming_2m | upcoming_5m | start
    invoked_by_scheduler: если True, уважается scheduler_enabled и не создаёт HTTPException из Bitrix (для фонового цикла).
    """
    mode_to_offset = {
        "upcoming_2m": 2,
        "upcoming_5m": 5,
        "start": 0,
    }
    if mode not in mode_to_offset:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"Unknown mode: {mode}",
            event=None,
            date=anchor_dispatch_at(at).date(),
            slot=0,
            start_time="",
        )

    duty_date, duty_slot, target_iso = _resolve_notification_slot(
        at=at,
        offset_minutes=mode_to_offset[mode],
    )
    if duty_date is None or duty_slot is None:
        return DutyNotificationDispatchOut(
            sent=False,
            reason=f"No duty slot at trigger moment ({target_iso})",
            event=mode,
            date=anchor_dispatch_at(at).date(),
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

    if invoked_by_scheduler and not bool(settings_row.scheduler_enabled):
        return DutyNotificationDispatchOut(
            sent=False,
            reason="Built-in scheduler is disabled in admin settings",
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

    enabled_upcoming_5m = bool(settings_row.cron_enabled_upcoming_5m)
    enabled_start = bool(settings_row.cron_enabled_start)
    enabled_chat_on_start = bool(settings_row.cron_enabled_chat_on_start)

    if mode == "upcoming_5m" and not enabled_upcoming_5m:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="Notifications 5 minutes before start are disabled in settings",
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
            reason="Start-of-duty personal notifications are disabled in settings",
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
        personal_message = _render_notification_template(
            settings_row.upcoming_5m_template,
            {
                "employee": user.full_name,
                "start_time": start_time,
                "date": assignment.date.isoformat(),
                "slot": str(assignment.slot),
            },
        )
        chat_message = ""
        need_personal = True
        need_chat = False
    else:  # start
        personal_message = _render_notification_template(
            settings_row.start_personal_template,
            {
                "employee": user.full_name,
                "start_time": start_time,
                "date": assignment.date.isoformat(),
                "slot": str(assignment.slot),
            },
        )
        chat_message = _render_notification_template(
            settings_row.start_chat_template,
            {
                "employee": bitrix_im_display_name(user),
                "start_time": start_time,
                "date": assignment.date.isoformat(),
                "slot": str(assignment.slot),
            },
        )
        need_personal = True
        need_chat = enabled_chat_on_start

    n8n_configured = bool(settings.N8N_WEBHOOK_URL and settings.N8N_WEBHOOK_URL.strip()) and bool(
        settings.N8N_DUTY_WEBHOOK_ENABLED
    )
    bitrix_url = bitrix_webhook_base_url()
    bitrix_pair: tuple[str, str] | None = None
    if need_chat:
        try:
            bitrix_pair = bitrix_messaging_pair_for_chat()
        except HTTPException as e:
            if invoked_by_scheduler:
                return DutyNotificationDispatchOut(
                    sent=False,
                    reason=f"Bitrix chat config: {e.detail}",
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
            raise

    if not n8n_configured and not bitrix_url and not bitrix_pair:
        return DutyNotificationDispatchOut(
            sent=False,
            reason="No notification channels configured (set BITRIX_INCOMING_WEBHOOK_URL and/or optional n8n)",
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
        req = UrllibRequest(
            settings.N8N_WEBHOOK_URL.strip(),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=settings.N8N_WEBHOOK_TIMEOUT_SEC):
                pass
        except HTTPError as e:
            if invoked_by_scheduler:
                # не роняем планировщик
                return DutyNotificationDispatchOut(
                    sent=False,
                    reason=f"n8n webhook error: {e.code}",
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
            raise HTTPException(status_code=502, detail=f"n8n webhook error: {e.code}") from e
        except URLError as e:
            if invoked_by_scheduler:
                return DutyNotificationDispatchOut(
                    sent=False,
                    reason="n8n webhook unavailable",
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

            def _send_p() -> None:
                bitrix_im_message_add(bitrix_url, str(user.bitrix_user_id), personal_message)

            if invoked_by_scheduler:
                try:
                    _send_p()
                    bitrix_personal_sent = True
                except HTTPException as e:
                    issues.append(f"Bitrix personal: {e.detail}")
                    bitrix_personal_sent = False
            else:
                _send_p()
                bitrix_personal_sent = True

    bitrix_chat_sent: bool | None = None
    if need_chat:
        if bitrix_pair is None:
            issues.append("Bitrix chat dialog is not configured")
            bitrix_chat_sent = False
        else:
            bx_url, bx_dialog = bitrix_pair

            def _send_c() -> None:
                bitrix_im_message_add(bx_url, bx_dialog, chat_message)

            if invoked_by_scheduler:
                try:
                    _send_c()
                    bitrix_chat_sent = True
                except HTTPException as e:
                    issues.append(f"Bitrix chat: {e.detail}")
                    bitrix_chat_sent = False
            else:
                _send_c()
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


def send_test_duty_notification(db, *, user_id: int) -> DutyTestNotificationOut:
    user = db.get(User, user_id)
    if not user:
        return DutyTestNotificationOut(
            sent=False,
            reason="User not found",
            user_id=user_id,
            full_name="",
            message="",
            bitrix_personal_sent=False,
        )
    today = today_moscow()
    settings_row = _get_or_create_notification_settings(db)
    assignment = db.execute(
        select(DutyAssignment)
        .where(DutyAssignment.support_user_id == user_id, DutyAssignment.date == today)
        .order_by(DutyAssignment.slot)
    ).scalars().first()
    if assignment:
        st = slot_start_time_str(assignment.slot)
        message = _render_notification_template(
            settings_row.test_with_slot_template,
            {
                "employee": user.full_name,
                "start_time": st,
                "date": today.isoformat(),
                "slot": str(assignment.slot),
            },
        )
    else:
        message = _render_notification_template(
            settings_row.test_without_slot_template,
            {
                "employee": user.full_name,
                "start_time": "—",
                "date": today.isoformat(),
                "slot": "—",
            },
        )

    bx = bitrix_webhook_base_url()
    if not bx:
        return DutyTestNotificationOut(
            sent=False,
            reason="BITRIX_INCOMING_WEBHOOK_URL is not configured",
            user_id=user.id,
            full_name=user.full_name,
            message=message,
            bitrix_personal_sent=False,
        )
    if user.bitrix_user_id is None:
        return DutyTestNotificationOut(
            sent=False,
            reason="У сотрудника не заполнен ID Битрикс (колонка «Битрикс» во вкладке Админ)",
            user_id=user.id,
            full_name=user.full_name,
            message=message,
            bitrix_personal_sent=False,
        )
    try:
        bitrix_im_message_add(bx, str(user.bitrix_user_id), message)
    except HTTPException as e:
        return DutyTestNotificationOut(
            sent=False,
            reason=str(e.detail),
            user_id=user.id,
            full_name=user.full_name,
            message=message,
            bitrix_personal_sent=False,
        )
    return DutyTestNotificationOut(
        sent=True,
        reason=None,
        user_id=user.id,
        full_name=user.full_name,
        message=message,
        bitrix_personal_sent=True,
    )
