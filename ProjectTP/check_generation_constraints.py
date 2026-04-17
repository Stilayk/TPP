"""
Happy-path: генерация с overwrite; слот 09:00 → логин user, макс. 2 дежурства/день на человека,
bootstrap-админ (TPP_BOOTSTRAP_ADMIN, по умолчанию как TPP_ADMIN_USER) не в графике от генерации.
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
BOOTSTRAP_USER = os.environ.get("TPP_BOOTSTRAP_ADMIN", ADMIN_USER).strip() or ADMIN_USER


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
    if not any(u.get("username") == "user" for u in users):
        raise SystemExit('В БД нужен активный сотрудник с логином "user" (слот 09:00).')

    bootstrap_id = next((u["id"] for u in users if u.get("username") == BOOTSTRAP_USER), None)

    start = date.today() + timedelta(days=14)
    end = start + timedelta(days=6)

    code, gen = call(
        opener,
        "/api/duties/generate",
        "POST",
        {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "overwrite": True,
        },
    )
    if code != 200:
        raise SystemExit(f"generate failed: {code} {gen}")
    if not isinstance(gen, dict) or "created_assignments" not in gen:
        raise SystemExit(f"generate unexpected: {gen}")

    d = start
    while d <= end:
        _, duties = call(opener, f"/api/duties?date={d.isoformat()}", "GET")
        slots = duties.get("slots") or []
        per_user: dict[int, int] = defaultdict(int)
        for s in slots:
            u = s.get("user")
            if u and u.get("id") is not None:
                per_user[int(u["id"])] += 1
            if s.get("start_time") == "09:00":
                if not u or u.get("username") != "user":
                    raise SystemExit(f"09:00 on {d} must be login 'user', got {u}")
        for uid, n in per_user.items():
            if n > 2:
                raise SystemExit(f"More than 2 duties same day user_id={uid} date={d}")
        if bootstrap_id is not None and per_user.get(bootstrap_id, 0) != 0:
            raise SystemExit(f"Bootstrap admin id={bootstrap_id} should not be in generated schedule on {d}")
        d += timedelta(days=1)

    print("generation_constraints_ok=true")


if __name__ == "__main__":
    main()
