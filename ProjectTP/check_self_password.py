import json
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def req(path, method="GET", body=None, use_cookie=True):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    client = opener if use_cookie else urllib.request.build_opener()
    try:
        with client.open(request, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8")
        try:
            parsed = json.loads(payload) if payload else None
        except Exception:
            parsed = {"raw": payload}
        return e.code, parsed


username = f"self{int(time.time())}"
old_password = "pass12345"
new_password = "newpass123"

req("/api/login", "POST", {"username": "admin", "password": "admin"})
status, user = req("/api/admin/users", "POST", {"username": username, "full_name": "Self Temp", "password": old_password})
print("create:", status, user["id"])
user_id = user["id"]

# user login old password should work
status, _ = req("/api/login", "POST", {"username": username, "password": old_password}, use_cookie=False)
print("login_old_before_change:", status)

# login as user in session and change own password
req("/api/login", "POST", {"username": username, "password": old_password})
status, body = req("/api/me/password", "POST", {"old_password": old_password, "new_password": new_password})
print("self_change:", status, body["ok"])

# old password now fails
status, body = req("/api/login", "POST", {"username": username, "password": old_password}, use_cookie=False)
print("login_old_after_change:", status, body.get("detail"))

# new password works
status, _ = req("/api/login", "POST", {"username": username, "password": new_password}, use_cookie=False)
print("login_new_after_change:", status)

# cleanup
req("/api/login", "POST", {"username": "admin", "password": "admin"})
status, _ = req(f"/api/admin/users/{user_id}", "DELETE")
print("cleanup_delete_user:", status)
