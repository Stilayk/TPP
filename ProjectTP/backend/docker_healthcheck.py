#!/usr/bin/env python3
"""Проверка готовности API для Docker healthcheck (таймаут, чтобы не зависать)."""
from __future__ import annotations

import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/api/health"
TIMEOUT_SEC = 4


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return 1
    except (urllib.error.URLError, TimeoutError, OSError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
