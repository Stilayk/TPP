from __future__ import annotations

import json
from io import BytesIO
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from urllib.error import HTTPError

from app.bitrix_notify import bitrix_im_message_add, normalize_bitrix_chat_dialog_id
from app.duty_notifications import _resolve_notification_slot


def _mock_urlopen_success(mock_urlopen: MagicMock, body: bytes) -> None:
    enter = MagicMock()
    enter.read.return_value = body
    mock_urlopen.return_value.__enter__.return_value = enter
    mock_urlopen.return_value.__exit__.return_value = None


@patch("app.bitrix_notify.urlopen")
def test_bitrix_im_message_add_success(mock_urlopen: MagicMock) -> None:
    _mock_urlopen_success(mock_urlopen, b'{"result":123}')
    bitrix_im_message_add("https://example.com/rest/1/token/", "6188", "Тестовое сообщение")
    mock_urlopen.assert_called_once()
    (req,), kwargs = mock_urlopen.call_args
    assert req.full_url == "https://example.com/rest/1/token/im.message.add.json"
    assert kwargs.get("timeout") is not None
    data = json.loads(req.data.decode("utf-8"))
    assert data == {"DIALOG_ID": "6188", "MESSAGE": "Тестовое сообщение"}


@patch("app.bitrix_notify.urlopen")
def test_bitrix_im_message_add_bitrix_error_json(mock_urlopen: MagicMock) -> None:
    err = json.dumps({"error": "ACCESS_DENIED", "error_description": "no im"}).encode("utf-8")
    _mock_urlopen_success(mock_urlopen, err)
    with pytest.raises(HTTPException) as ei:
        bitrix_im_message_add("https://example.com/rest/1/t/", "1", "x")
    assert ei.value.status_code == 502
    assert "bitrix" in (ei.value.detail or "").lower()


@patch("app.bitrix_notify.urlopen")
def test_bitrix_im_message_add_http_error_body(mock_urlopen: MagicMock) -> None:
    body = json.dumps(
        {"error": "CANCELED", "error_description": "Вы не можете отправлять сообщения в указанный чат"},
    ).encode("utf-8")
    http_err = HTTPError("https://example.com/rest/1/t/im.message.add.json", 400, "Bad Request", None, BytesIO(body))
    mock_urlopen.side_effect = http_err
    with pytest.raises(HTTPException) as ei:
        bitrix_im_message_add("https://example.com/rest/1/t/", "chat1", "x")
    assert ei.value.status_code == 502
    assert "400" in (ei.value.detail or "")
    assert "указанный чат" in (ei.value.detail or "") or "CANCELED" in (ei.value.detail or "")


def test_resolve_notification_slot_hits_start_of_slot() -> None:
    duty_date, duty_slot, _ = _resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 55, 0),
        offset_minutes=5,
    )
    assert duty_date is not None
    assert duty_slot == 3  # 10:00 slot when SLOT_START_HOUR=07:00


def test_normalize_bitrix_chat_dialog_id_numeric() -> None:
    assert normalize_bitrix_chat_dialog_id("2237493") == "chat2237493"


def test_normalize_bitrix_chat_dialog_id_explicit_chat() -> None:
    assert normalize_bitrix_chat_dialog_id("chat2237493") == "chat2237493"


def test_resolve_notification_slot_ignores_non_trigger_minutes() -> None:
    duty_date, duty_slot, _ = _resolve_notification_slot(
        at=datetime(2026, 4, 15, 9, 56, 0),
        offset_minutes=5,
    )
    assert duty_date is None
    assert duty_slot is None
