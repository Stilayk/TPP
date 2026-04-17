from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException

from app.config import settings


def bitrix_webhook_base_url() -> str | None:
    bx_url = (settings.BITRIX_INCOMING_WEBHOOK_URL or "").strip()
    return bx_url or None


def normalize_bitrix_chat_dialog_id(raw: str) -> str:
    """Групповой чат в Битрикс24: `chatNNN`; если задано только число — добавляем префикс."""
    s = (raw or "").strip()
    if not s:
        return ""
    lowered = s.lower()
    if lowered.startswith("chat") or lowered.startswith("imol|"):
        return s
    if s.isdigit():
        return f"chat{s}"
    return s


def bitrix_messaging_pair_for_chat() -> tuple[str, str] | None:
    """Пара URL вебхука + ID диалога общего чата (im.message.add)."""
    bx_url = (settings.BITRIX_INCOMING_WEBHOOK_URL or "").strip()
    bx_dialog_raw = (settings.BITRIX_NOTIFY_DIALOG_ID or "").strip()
    bx_dialog = normalize_bitrix_chat_dialog_id(bx_dialog_raw)
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


def bitrix_im_message_add(base_url: str, dialog_id: str, message: str) -> None:
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
