#!/usr/bin/env python3
"""
Ручная проверка отправки в Битрикс (im.message.add).

Подставьте переменные в окружение или в ProjectTP/.env рядом с этим скриптом:
  BITRIX_INCOMING_WEBHOOK_URL, BITRIX_NOTIFY_DIALOG_ID (формат как в im.message.add: чат — chatNNN)

Запуск из каталога ProjectTP:
  python3 check_bitrix_message.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    root = Path(__file__).resolve().parent
    _load_env_file(root / ".env")

    base = (os.environ.get("BITRIX_INCOMING_WEBHOOK_URL") or "").strip().rstrip("/") + "/"
    dialog = (os.environ.get("BITRIX_NOTIFY_DIALOG_ID") or "").strip()
    if not base or base == "/" or not dialog:
        print("Задайте BITRIX_INCOMING_WEBHOOK_URL и BITRIX_NOTIFY_DIALOG_ID (.env или окружение).", file=sys.stderr)
        return 1

    url = f"{base}im.message.add.json"
    body = json.dumps(
        {"DIALOG_ID": dialog, "MESSAGE": "[duty-app] Проверка отправки сообщения"},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
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
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Ответ не JSON", file=sys.stderr)
        return 4
    if isinstance(data, dict) and data.get("error"):
        print("Bitrix error:", data.get("error_description") or data.get("error"), file=sys.stderr)
        return 5
    print("OK: сообщение должно появиться в чате / диалоге.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
