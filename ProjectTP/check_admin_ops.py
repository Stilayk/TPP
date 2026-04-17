import json
import time
import urllib.request

base = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def req(path, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with opener.open(r, timeout=10) as resp:
        payload = resp.read().decode("utf-8")
        return resp.status, (json.loads(payload) if payload else None)


status, _ = req("/api/login", "POST", {"username": "admin", "password": "admin"})
print("login:", status)

username = f"u{int(time.time())}"
status, user = req("/api/admin/users", "POST", {"username": username, "full_name": "Temp User", "password": "pass12345"})
user_id = user["id"]
print("create:", status, user_id)

status, res = req(f"/api/admin/users/{user_id}/password", "POST", {"new_password": "newpass123"})
print("change_password:", status, res["ok"])

status, res = req(f"/api/admin/users/{user_id}/reports", "DELETE")
print("delete_reports:", status, res["deleted_reports"])

status, res = req(f"/api/admin/users/{user_id}", "DELETE")
print("delete_user:", status, res["ok"])
