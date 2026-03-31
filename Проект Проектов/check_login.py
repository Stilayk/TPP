import json
import urllib.error
import urllib.request

urls = ["http://127.0.0.1:8080/api/login", "http://127.0.0.1:8000/api/login"]
payload = json.dumps({"username": "admin", "password": "admin"}).encode("utf-8")

for url in urls:
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            print(url, resp.status, resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        print(url, err.code, err.read().decode("utf-8"))
    except Exception as err:
        print(url, type(err).__name__, str(err))
