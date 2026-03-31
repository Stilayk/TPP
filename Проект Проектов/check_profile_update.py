import json
import time
import urllib.request

BASE = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def request(path, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with opener.open(req, timeout=8) as resp:
        payload = resp.read().decode("utf-8")
        return resp.status, (json.loads(payload) if payload else None)


username = f"profile{int(time.time())}"
password = "pass12345"

request("/api/login", "POST", {"username": "admin", "password": "admin"})
_, user = request("/api/admin/users", "POST", {"username": username, "full_name": "Before Name", "password": password})

request("/api/login", "POST", {"username": username, "password": password})
status, me = request("/api/me/profile", "PATCH", {"full_name": "After Name"})
print("patch_profile:", status, me["full_name"])

status, me = request("/api/me")
print("me_after_patch:", status, me["full_name"])

request("/api/login", "POST", {"username": "admin", "password": "admin"})
request(f"/api/admin/users/{user['id']}", "DELETE")
