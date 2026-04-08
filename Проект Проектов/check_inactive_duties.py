import json
import time
import urllib.request

BASE = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def req(path, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with opener.open(request, timeout=10) as resp:
        payload = resp.read().decode("utf-8")
        return resp.status, (json.loads(payload) if payload else None)


req("/api/login", "POST", {"username": "admin", "password": "admin"})

t = int(time.time())
_, u1 = req("/api/admin/users", "POST", {"username": f"act{t}", "full_name": "Active User", "password": "pass12345"})
_, u2 = req("/api/admin/users", "POST", {"username": f"inact{t}", "full_name": "Inactive User", "password": "pass12345"})

status, _ = req(f"/api/admin/users/{u2['id']}/duty-status", "PATCH", {"is_active_for_duties": False})
print("set_inactive:", status)

status, _ = req("/api/duties/generate", "POST", {"start_date": "2026-04-01", "end_date": "2026-04-01", "overwrite": True})
print("generate:", status)

_, duties = req("/api/duties?date=2026-04-01", "GET")
ids = [slot["user"]["id"] for slot in duties["slots"] if slot.get("user")]
print("used_user_ids:", sorted(set(ids)))
print("inactive_present:", u2["id"] in ids)

req(f"/api/admin/users/{u1['id']}", "DELETE")
req(f"/api/admin/users/{u2['id']}", "DELETE")
