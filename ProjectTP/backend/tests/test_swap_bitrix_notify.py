from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routers.duty_swaps import notify_duty_swap_target_bitrix


def test_notify_swap_skips_without_webhook() -> None:
    r = SimpleNamespace(full_name="Инициатор", username="a", bitrix_user_id=1)
    t = SimpleNamespace(full_name="Цель", username="b", bitrix_user_id=2)
    with patch("app.routers.duty_swaps.bitrix_webhook_base_url", return_value=None):
        notify_duty_swap_target_bitrix(
            requester=r, target_user=t, swap_date=date(2026, 5, 14), from_slot=0, to_slot=1
        )


@patch("app.routers.duty_swaps.bitrix_im_message_add")
def test_notify_swap_sends_personal(mock_add) -> None:
    r = SimpleNamespace(full_name="Инициатор", username="a", bitrix_user_id=10)
    t = SimpleNamespace(full_name="Цель", username="b", bitrix_user_id=20)
    with patch("app.routers.duty_swaps.bitrix_webhook_base_url", return_value="https://example.com/rest/1/t/"):
        notify_duty_swap_target_bitrix(
            requester=r, target_user=t, swap_date=date(2026, 5, 14), from_slot=0, to_slot=1
        )
    mock_add.assert_called_once()
    assert mock_add.call_args[0][1] == "20"
    assert "обменяться" in mock_add.call_args[0][2]


@patch("app.routers.duty_swaps.bitrix_im_message_add", side_effect=HTTPException(status_code=502, detail="x"))
def test_notify_swap_logs_bitrix_error(mock_add) -> None:
    r = SimpleNamespace(full_name="Инициатор", username="a", bitrix_user_id=10)
    t = SimpleNamespace(full_name="Цель", username="b", bitrix_user_id=20)
    with patch("app.routers.duty_swaps.bitrix_webhook_base_url", return_value="https://example.com/rest/1/t/"):
        notify_duty_swap_target_bitrix(
            requester=r, target_user=t, swap_date=date(2026, 5, 14), from_slot=0, to_slot=1
        )
    mock_add.assert_called_once()
