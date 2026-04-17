import json
import urllib.request

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

login_req = urllib.request.Request(
    "http://127.0.0.1:8080/api/login",
    data=json.dumps({"username": "admin", "password": "admin"}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with opener.open(login_req, timeout=8):
    pass

with opener.open("http://127.0.0.1:8080/api/admin/users", timeout=8) as resp:
    users = json.loads(resp.read().decode("utf-8"))

for u in users:
    print(f"id={u['id']} login={u['username']} full_name={u['full_name']}")
