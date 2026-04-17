#!/usr/bin/env python3
"""Один раз: график дежурств из БД → сообщение в Битрикс (im.message.add). Запуск в контейнере backend."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from sqlalchemy import select

_root = Path("/app/backend") if Path("/app/backend/app").is_dir() else Path.cwd()
sys.path.insert(0, str(_root))

from app.bitrix_mention import bitrix_im_display_name  # noqa: E402
from app.bitrix_notify import normalize_bitrix_chat_dialog_id  # noqa: E402
from app.database import db_session  # noqa: E402
from app.duty_slots import SLOT_COUNT, slot_start_time_str  # noqa: E402
from app.models import DutyAssignment, User  # noqa: E402


def _parse_date_arg() -> date:
    if len(sys.argv) > 1:
        return date.fromisoformat(sys.argv[1])
    return date.today()


def main() -> int:
    target = _parse_date_arg()
    # compose пробрасывает BITRIX_* в окружение; не зависим от полей Settings в образе
    bx_url = (os.environ.get("BITRIX_INCOMING_WEBHOOK_URL") or "").strip().rstrip("/") + "/"
    dialog = normalize_bitrix_chat_dialog_id(os.environ.get("BITRIX_NOTIFY_DIALOG_ID") or "")
    if not bx_url or bx_url == "/" or not dialog:
        print("В окружении backend задайте BITRIX_INCOMING_WEBHOOK_URL и BITRIX_NOTIFY_DIALOG_ID.", file=sys.stderr)
        return 1

    with db_session() as db:
        rows = db.execute(
            select(DutyAssignment, User)
            .join(User, DutyAssignment.support_user_id == User.id)
            .where(DutyAssignment.date == target)
        ).all()
    by_slot: dict[int, User] = {a.slot: u for a, u in rows}

    lines = [f"Дежурства на {target.isoformat()}:"]
    for slot in range(0, SLOT_COUNT):
        t = slot_start_time_str(slot)
        u = by_slot.get(slot)
        lines.append(f"{t} — {bitrix_im_display_name(u)}" if u else f"{t} — не назначено")
    message = "\n".join(lines)

    url = f"{bx_url}im.message.add.json"
    body = json.dumps({"DIALOG_ID": dialog, "MESSAGE": message}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    timeout = int(os.environ.get("BITRIX_WEBHOOK_TIMEOUT_SEC") or "10")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print("Сеть:", e.reason, file=sys.stderr)
        return 3

    print(raw)
    data = json.loads(raw)
    if isinstance(data, dict) and data.get("error"):
        print("Bitrix:", data.get("error_description") or data.get("error"), file=sys.stderr)
        return 4
    print("OK: список отправлен в чат", dialog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
