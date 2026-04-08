"""
Happy-path: выдача и отзыв прав администратора (P1 №23); изначального админа снять нельзя (если задан BOOTSTRAP_ADMIN_USERNAME).
Запуск: прокси или nginx на BASE (по умолчанию http://127.0.0.1:8080), admin в .env / дефолт.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("TPP_API_BASE", "http://127.0.0.1:8080")
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
            payload = resp.read().decode("utf-8")
            if payload and "application/json" in resp.headers.get("content-type", ""):
                return resp.status, json.loads(payload)
            return resp.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def main():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    code, _ = call(opener, "/api/login", "POST", {"username": ADMIN_USER, "password": ADMIN_PASS})
    if code != 200:
        raise SystemExit(f"admin login failed: {code}")

    code, users = call(opener, "/api/admin/users", "GET")
    if code != 200:
        raise SystemExit(f"list users failed: {code}")
    bootstrap = next((u for u in users if u.get("username") == ADMIN_USER and u.get("role") == "admin"), None)
    if not bootstrap:
        raise SystemExit("bootstrap admin not found in user list")

    t = int(time.time())
    username = f"deleg{t}"
    code, created = call(
        opener,
        "/api/admin/users",
        "POST",
        {"username": username, "full_name": "Delegate Temp", "password": "pass12345"},
    )
    if code != 200:
        raise SystemExit(f"create support failed: {code} {created}")
    uid = int(created["id"])

    code, promoted = call(opener, f"/api/admin/users/{uid}/grant-admin", "POST", {})
    if code != 200 or promoted.get("role") != "admin":
        raise SystemExit(f"grant-admin failed: {code} {promoted}")

    code, err = call(opener, f"/api/admin/users/{bootstrap['id']}/revoke-admin", "POST", {})
    if bootstrap.get("is_bootstrap_admin"):
        if code != 400:
            raise SystemExit(f"expected 400 revoke bootstrap forbidden, got {code}: {err}")
    else:
        if code != 200:
            raise SystemExit(f"without BOOTSTRAP_ADMIN_USERNAME expected 200 demote bootstrap, got {code}: {err}")
        code, _ = call(opener, "/api/login", "POST", {"username": username, "password": "pass12345"})
        if code != 200:
            raise SystemExit("login as temp admin for restore failed")
        code, _ = call(opener, f"/api/admin/users/{bootstrap['id']}/grant-admin", "POST", {})
        if code != 200:
            raise SystemExit("grant-admin restore bootstrap failed")
        code, _ = call(opener, "/api/login", "POST", {"username": ADMIN_USER, "password": ADMIN_PASS})
        if code != 200:
            raise SystemExit("re-login bootstrap after restore failed")

    code, _ = call(opener, f"/api/admin/users/{uid}/revoke-admin", "POST", {})
    if code != 200:
        raise SystemExit("revoke temp admin failed")

    code, err = call(opener, f"/api/admin/users/{bootstrap['id']}/revoke-admin", "POST", {})
    if code != 400:
        raise SystemExit(f"expected 400 sole admin / bootstrap, got {code}: {err}")

    code, _ = call(opener, f"/api/admin/users/{uid}", "DELETE")
    if code != 200:
        raise SystemExit(f"cleanup delete failed: {code}")

    print("check_admin_delegate: OK")


if __name__ == "__main__":
    main()
