import json
import urllib.request

TARGET_LOGINS = {"u1774953477", "u1774953502"}
BASE = "http://127.0.0.1:8080"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

login_req = urllib.request.Request(
    BASE + "/api/login",
    data=json.dumps({"username": "admin", "password": "admin"}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with opener.open(login_req, timeout=8):
    pass

with opener.open(BASE + "/api/admin/users", timeout=8) as resp:
    users = json.loads(resp.read().decode("utf-8"))

targets = [u for u in users if u["username"] in TARGET_LOGINS]
for u in targets:
    req = urllib.request.Request(BASE + f"/api/admin/users/{u['id']}", method="DELETE")
    with opener.open(req, timeout=8) as resp:
        print(f"deleted id={u['id']} login={u['username']} status={resp.status}")

with opener.open(BASE + "/api/admin/users", timeout=8) as resp:
    users_after = json.loads(resp.read().decode("utf-8"))

remaining = [u["username"] for u in users_after if u["username"] in TARGET_LOGINS]
print("remaining:", remaining)
