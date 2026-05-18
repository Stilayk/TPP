import json
import os
import urllib.request
import urllib.error

BASE = os.environ.get("CHECK_BASE", "http://127.0.0.1:8000")
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
        try:
            parsed = json.loads(payload) if payload else None
        except Exception:
            parsed = {"raw": payload}
        return e.code, parsed


def req_bin(path, method="POST", body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


status, ping = req("/api/ee_instruction/ping")
print("ping:", status, ping)
assert status == 200 and (ping or {}).get("ok") is True

status, _ = req("/api/login", "POST", {"username": "admin", "password": "admin"})
print("login:", status)

status, gen = req(
    "/api/ee_instruction",
    "POST",
    {
        "fio": "Иванов Иван Иванович",
        "login": "ivanovii",
        "password": "TempPass123",
        "domain": "rz",
    },
)
print("generate:", status, "len_text", len((gen or {}).get("text") or ""))

assert status == 200
text = (gen or {}).get("text") or ""
assert "Иванов Иван Иванович" in text
assert "ivanovii" in text
assert "TempPass123" in text
assert "Sokolov" in text
assert "portal.hpdd.ru" in text
assert "Ваш домен" in text and "rz" in text
assert r"rz\ivanovii" in text

status, raw = req_bin(
    "/api/ee_instruction/docx",
    "POST",
    {
        "fio": "Иванов Иван Иванович",
        "login": "ivanovii",
        "password": "TempPass123",
        "domain": "rz",
    },
)
print("docx:", status, "bytes", len(raw))
assert status == 200
assert raw[:2] == b"PK"

status, share = req(
    "/api/ee_instruction/share",
    "POST",
    {
        "fio": "Иванов Иван Иванович",
        "login": "ivanovii",
        "password": "TempPass123",
        "domain": "rz",
        "public_base_url": BASE,
    },
)
print("share:", status, share)
assert status == 200
token = (share or {}).get("token") or ""
pub = (share or {}).get("public_url") or ""
assert token and pub.endswith("/p/ee/" + token)

req_plain = urllib.request.Request(BASE + "/p/ee/" + token, method="GET")
with urllib.request.urlopen(req_plain, timeout=10) as resp:
    assert resp.status == 200
    html_body = resp.read().decode("utf-8")
assert "Иванов Иван Иванович" in html_body

st_qr, png = req_bin("/api/ee_instruction/qr/" + token, "GET", None)
print("qr_png:", st_qr, "bytes", len(png))
assert st_qr == 200
assert isinstance(png, (bytes, bytearray)) and png[:8] == b"\x89PNG\r\n\x1a\n"

print("ok")
