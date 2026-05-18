"""
Happy-path: после генерации графика суммы назначений по активным support-пользователям
отличаются не более чем на 1 (полный overwrite, один непрерывный диапазон дат).
Запуск: backend на BASE (по умолчанию http://127.0.0.1:8000), учётная запись admin.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from rf_calendar_for_checks import is_day_skipped_by_auto_generation

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
        if u.get("role") in ("support", "admin")
        and u.get("is_active_for_duties", True) is not False
        and not u.get("is_bootstrap_admin")
    ]
    if len(support_ids) < 2:
        raise SystemExit("Need at least 2 active non-bootstrap support or admin users for fairness check.")

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

    d = start
    weekday_slot_patterns: list[tuple] = []
    while d <= end:
        if not is_day_skipped_by_auto_generation(d):
            _, duties = call(opener, f"/api/duties?date={d.isoformat()}", "GET")
            slots = sorted(duties.get("slots") or [], key=lambda s: int(s.get("slot") or 0))
            ids = tuple(((s.get("user") or {}).get("id")) for s in slots)
            if len(ids) == 11 and all(i is not None for i in ids):
                weekday_slot_patterns.append(ids)
        d += timedelta(days=1)
    if (
        len(support_ids) >= 12
        and len(weekday_slot_patterns) >= 2
        and len(set(weekday_slot_patterns)) < 2
    ):
        raise SystemExit(
            "generation TASK67: identical (slot order → user id) vectors on multiple weekdays in range; "
            "check duty_generation flush / multi-day logic."
        )

    d = start
    while d <= end:
        if is_day_skipped_by_auto_generation(d):
            _, duties = call(opener, f"/api/duties?date={d.isoformat()}", "GET")
            for s in duties.get("slots") or []:
                if s.get("user"):
                    raise SystemExit(
                        f"non-working day {d.isoformat()} must have no generated duties, got slot {s.get('slot')}"
                    )
        d += timedelta(days=1)

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

    per_day_max = 0
    d = start
    while d <= end:
        _, duties = call(opener, f"/api/duties?date={d.isoformat()}", "GET")
        slots = duties.get("slots") or []
        day_n: dict[int, int] = defaultdict(int)
        for s in slots:
            u = s.get("user")
            if u and u.get("id") is not None:
                day_n[int(u["id"])] += 1
        if day_n:
            per_day_max = max(per_day_max, max(day_n.values()))
        d += timedelta(days=1)
    max2_ok = per_day_max <= 2

    print(
        f"fairness_ok={ok} delta={delta} max_slots_per_user_per_day={per_day_max} max2_ok={max2_ok} "
        f"counts={dict((k, counts[k]) for k in support_ids)}"
    )
    if not ok or not max2_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
