from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.duty_notification_slot import RELAXED_SLOT_TOLERANCE, resolve_notification_slot
from app.duty_notifications_runtime import apply_monkeypatches
from app.models import DutyNotificationSettings


def test_resolve_strict_hits_slot() -> None:
    duty_date, duty_slot, _ = resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 55, 0),
        offset_minutes=5,
        strict_timing=True,
    )
    assert duty_date == date(2026, 4, 15)
    assert duty_slot == 3


def test_resolve_strict_rejects_off_minute() -> None:
    duty_date, duty_slot, _ = resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 56, 0),
        offset_minutes=5,
        strict_timing=True,
    )
    assert duty_date is None
    assert duty_slot is None


def test_resolve_relaxed_maps_drifted_cron() -> None:
    duty_date, duty_slot, _ = resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 56, 0),
        offset_minutes=5,
        strict_timing=False,
    )
    assert duty_date == date(2026, 4, 15)
    assert duty_slot == 3


def test_resolve_relaxed_too_far_from_hour() -> None:
    duty_date, duty_slot, _ = resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 40, 0),
        offset_minutes=5,
        strict_timing=False,
    )
    assert duty_date is None
    assert duty_slot is None


def test_dispatch_upcoming_5m_happy_bitrix_only() -> None:
    apply_monkeypatches()
    from app.duty_notifications import dispatch_duty_notification

    settings_row = MagicMock(
        scheduler_enabled=True,
        cron_enabled_upcoming_5m=True,
        cron_enabled_start=True,
        cron_enabled_chat_on_start=True,
    )
    assign = MagicMock()
    assign.date = date(2026, 4, 15)
    assign.slot = 3
    user = MagicMock()
    user.id = 1
    user.full_name = "Тест Т."
    user.username = "test"
    user.bitrix_user_id = 6188

    mock_db = MagicMock()

    def get_side_effect(model, pk):
        if model is DutyNotificationSettings and pk == 1:
            return settings_row
        return None

    mock_db.get.side_effect = get_side_effect
    exec_res = MagicMock()
    exec_res.first.return_value = (assign, user)
    mock_db.execute.return_value = exec_res

    with (
        patch("app.duty_notifications.settings") as st,
        patch("app.duty_notifications.bitrix_webhook_base_url", return_value="https://example.com/rest/1/t/"),
        patch("app.duty_notifications.bitrix_im_message_add") as bx,
    ):
        st.N8N_WEBHOOK_URL = ""
        st.N8N_DUTY_WEBHOOK_ENABLED = False
        out = dispatch_duty_notification(
            mock_db,
            mode="upcoming_5m",
            at=datetime(2026, 4, 15, 9, 55, 0),
            invoked_by_scheduler=False,
            strict_timing=True,
        )
    assert out.sent is True
    assert out.bitrix_personal_sent is True
    bx.assert_called_once()
    args = bx.call_args[0]
    assert "6188" in args[1]


def test_dispatch_relaxed_time_sends() -> None:
    apply_monkeypatches()
    from app.duty_notifications import dispatch_duty_notification

    settings_row = MagicMock(
        scheduler_enabled=True,
        cron_enabled_upcoming_5m=True,
        cron_enabled_start=True,
        cron_enabled_chat_on_start=True,
    )
    assign = MagicMock()
    assign.date = date(2026, 4, 15)
    assign.slot = 3
    user = MagicMock()
    user.id = 1
    user.full_name = "Тест Т."
    user.username = "test"
    user.bitrix_user_id = 1

    mock_db = MagicMock()

    def get_side_effect(model, pk):
        if model is DutyNotificationSettings and pk == 1:
            return settings_row
        return None

    mock_db.get.side_effect = get_side_effect
    exec_res = MagicMock()
    exec_res.first.return_value = (assign, user)
    mock_db.execute.return_value = exec_res

    with (
        patch("app.duty_notifications.settings") as st,
        patch("app.duty_notifications.bitrix_webhook_base_url", return_value="https://example.com/rest/1/t/"),
        patch("app.duty_notifications.bitrix_im_message_add") as bx,
    ):
        st.N8N_WEBHOOK_URL = ""
        st.N8N_DUTY_WEBHOOK_ENABLED = False
        out = dispatch_duty_notification(
            mock_db,
            mode="upcoming_5m",
            at=datetime(2026, 4, 15, 9, 56, 0),
            invoked_by_scheduler=False,
            strict_timing=False,
        )
    assert out.sent is True
    bx.assert_called_once()


def test_relaxed_tolerance_constant() -> None:
    assert RELAXED_SLOT_TOLERANCE.total_seconds() == 180
