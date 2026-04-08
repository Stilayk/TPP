import json
import time
import urllib.error
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
    try:
        with opener.open(request, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
            return resp.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8")
        return e.code, (json.loads(payload) if payload else None)


test_date = "2026-04-02"

req("/api/login", "POST", {"username": "admin", "password": "admin"})

t = int(time.time())
_, u1 = req("/api/admin/users", "POST", {"username": f"swapa{t}", "full_name": "Иванов Владимир", "password": "pass12345"})
_, u2 = req("/api/admin/users", "POST", {"username": f"swapb{t}", "full_name": "Ревин Сергей", "password": "pass12345"})

assignments = [
    {"slot": 0, "user_id": u1["id"]},
    {"slot": 1, "user_id": u2["id"]},
    {"slot": 2, "user_id": u1["id"]},
    {"slot": 3, "user_id": u2["id"]},
    {"slot": 4, "user_id": u1["id"]},
    {"slot": 5, "user_id": u2["id"]},
    {"slot": 6, "user_id": u1["id"]},
    {"slot": 7, "user_id": u2["id"]},
    {"slot": 8, "user_id": u1["id"]},
]
req("/api/duties/batch", "POST", {"date": test_date, "assignments": assignments})
req("/api/logout", "POST")

req("/api/login", "POST", {"username": u1["username"], "password": "pass12345"})

status_ok, _ = req("/api/duty-swaps", "POST", {"date": test_date, "from_slot": 0, "to_slot": 1})
print("create_swap_to_other:", status_ok)

status_self, body_self = req("/api/duty-swaps", "POST", {"date": test_date, "from_slot": 0, "to_slot": 2})
print("create_swap_to_self:", status_self, body_self.get("detail") if isinstance(body_self, dict) else body_self)
req("/api/logout", "POST")

req("/api/login", "POST", {"username": u2["username"], "password": "pass12345"})
status_inbox, inbox = req(f"/api/duty-swaps/inbox?date={test_date}", "GET")
print("inbox_status:", status_inbox)
print("inbox_count:", len(inbox or []))
print("inbox_first_message:", (inbox or [{}])[0].get("message"))
swap_id = (inbox or [{}])[0].get("id")
status_accept, body_accept = req(f"/api/duty-swaps/{swap_id}/decision", "POST", {"action": "accept"})
print("accept_status:", status_accept, body_accept.get("status") if isinstance(body_accept, dict) else body_accept)
req("/api/logout", "POST")

req("/api/login", "POST", {"username": u1["username"], "password": "pass12345"})
_, duties_after = req(f"/api/duties?date={test_date}", "GET")
slot0 = (duties_after.get("slots") or [{}])[0].get("user", {}).get("id")
slot1 = (duties_after.get("slots") or [{}, {}])[1].get("user", {}).get("id")
print("after_accept_slot0_user:", slot0)
print("after_accept_slot1_user:", slot1)
req("/api/logout", "POST")

req("/api/login", "POST", {"username": "admin", "password": "admin"})
req(f"/api/admin/users/{u1['id']}", "DELETE")
req(f"/api/admin/users/{u2['id']}", "DELETE")
