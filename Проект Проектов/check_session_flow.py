import json
import urllib.request

base = "http://127.0.0.1:8080"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

# login
login_req = urllib.request.Request(
    base + "/api/login",
    data=json.dumps({"username": "admin", "password": "admin"}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with opener.open(login_req, timeout=8) as r:
    print("login:", r.status, r.read().decode("utf-8"))

# me with session cookie
with opener.open(base + "/api/me", timeout=8) as r:
    print("me:", r.status, r.read().decode("utf-8"))
