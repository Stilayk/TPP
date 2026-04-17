"""
Happy-path: после генерации графика суммы назначений по активным support-пользователям
отличаются не более чем на 1 (полный overwrite, один непрерывный диапазон дат).
Запуск: backend на BASE (по умолчанию http://127.0.0.1:8000), учётная запись admin.
"""
import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

BASE = os.environ.get("TPP_API_BASE", "http://127.0.0.1:8000")
ADMIN_USER = os.environ.get("TPP_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("TPP_ADMIN_PASS", "admin")


def call(opener, path, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=20) as resp:
            payload = resp.read()
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype and payload:
                return resp.status, json.loads(payload.decode("utf-8"))
            return resp.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed


def main():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    code, _ = call(opener, "/api/login", "POST", {"username": ADMIN_USER, "password": ADMIN_PASS})
    if code != 200:
        raise SystemExit(f"admin login failed: {code}")

    _, users = call(opener, "/api/admin/users", "GET")
    support_ids = [
        u["id"]
        for u in users
        if u.get("role") in ("support", "admin") and u.get("is_active_for_duties", True) is not False
    ]
    if len(support_ids) < 2:
        raise SystemExit("Need at least 2 active support or admin users in DB for fairness check.")

    # Диапазон в будущем, чтобы не задевать текущие ручные правки
    start = date.today() + timedelta(days=14)
    end = start + timedelta(days=6)

    _, gen = call(
        opener,
        "/api/duties/generate",
        "POST",
        {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "overwrite": True,
        },
    )
    if not isinstance(gen, dict) or "created_assignments" not in gen:
        raise SystemExit(f"generate unexpected: {gen}")

    counts: dict[int, int] = defaultdict(int)
    d = start
    while d <= end:
        _, duties = call(opener, f"/api/duties?date={d.isoformat()}", "GET")
        slots = duties.get("slots") or []
        for s in slots:
            u = s.get("user")
            if u and u.get("id") is not None:
                counts[int(u["id"])] += 1
        d += timedelta(days=1)

    for uid in support_ids:
        counts.setdefault(uid, 0)
    vals = [counts[uid] for uid in support_ids]
    delta = max(vals) - min(vals) if vals else 0
    ok = delta <= 1
    print(f"fairness_ok={ok} delta={delta} counts={dict((k, counts[k]) for k in support_ids)}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
