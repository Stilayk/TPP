import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8080"
EXPORTS_DIR = Path("C:/Users/zomof/Documents/TPP/5A2F~1/backend/exports")


def call(opener, path, method="GET", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=12) as resp:
            payload = resp.read()
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype and payload:
                return resp.status, json.loads(payload.decode("utf-8"))
            return resp.status, payload
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8")
        try:
            parsed = json.loads(payload) if payload else None
        except Exception:
            parsed = {"raw": payload}
        return e.code, parsed


admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
support = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
guest = urllib.request.build_opener()

t = int(time.time())
username = f"excel{t}"
password = "pass12345"
date_str = "2026-04-02"

call(admin, "/api/login", "POST", {"username": "admin", "password": "admin"})
_, created = call(admin, "/api/admin/users", "POST", {"username": username, "full_name": "Excel User", "password": password})
uid = created["id"]

call(support, "/api/login", "POST", {"username": username, "password": password})
_, report = call(support, "/api/reports", "POST", {"date": date_str})
rid = report["report_id"]
call(support, f"/api/reports/{rid}", "PUT", {"entries": [{"minutes": 10, "description": "smoke"}]})

status, fin = call(support, f"/api/reports/{rid}/finalize", "POST")
excel_url = fin["excel_url"]
print("finalize:", status, excel_url)

status, payload = call(support, excel_url, "GET")
print("download_as_owner:", status, len(payload) if isinstance(payload, (bytes, bytearray)) else payload)

status, payload = call(guest, excel_url, "GET")
print("download_as_guest:", status, payload.get("detail") if isinstance(payload, dict) else "no-json")

# remove file and verify self-healing
filename = excel_url.split("/")[-1]
file_path = EXPORTS_DIR / filename
if file_path.exists():
    os.remove(file_path)
status, fin2 = call(support, f"/api/reports/{rid}/finalize", "POST")
print("finalize_after_file_delete:", status, fin2["excel_url"])
status, payload = call(support, excel_url, "GET")
print("download_after_rebuild:", status, len(payload) if isinstance(payload, (bytes, bytearray)) else payload)

call(admin, f"/api/admin/users/{uid}/reports", "DELETE")
call(admin, f"/api/admin/users/{uid}", "DELETE")
