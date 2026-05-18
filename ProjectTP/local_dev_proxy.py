import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BACKEND = "http://127.0.0.1:8000"
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def send_error(self, code, message=None, explain=None):
        path_only = (self.path or "").split("?", 1)[0]
        if path_only.startswith("/api/") or path_only.startswith("/exports/") or path_only.startswith("/p/"):
            detail = f"HTTP {code}"
            if message:
                detail = f"{detail}: {message}"
            if explain:
                detail = f"{detail} ({explain})"
            body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass
            return
        super().send_error(code, message, explain)

    def do_GET(self):
        if self.path.startswith("/api/") or self.path.startswith("/exports/") or self.path.startswith("/p/"):
            self._proxy()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        self.send_error(404)

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        self.send_error(404)

    def _proxy(self):
        body = None
        if "Content-Length" in self.headers:
            body = self.rfile.read(int(self.headers["Content-Length"]))

        req = Request(
            BACKEND + self.path,
            data=body,
            method=self.command,
            headers={k: v for k, v in self.headers.items() if k.lower() != "host"},
        )
        try:
            with urlopen(req, timeout=15) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in {"transfer-encoding", "connection"}:
                        continue
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() in {"transfer-encoding", "connection"}:
                    continue
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except URLError as e:
            # Чтобы UI не получал HTML-страницу ошибки вместо JSON при fetch("/api/...").
            body = json.dumps(
                {
                    "detail": "Backend недоступен: запустите PostgreSQL и uvicorn на 127.0.0.1:8000 "
                    f"(см. deployment_and_tz_request.md). Причина: {e!s}",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = json.dumps(
                {
                    "detail": "Ошибка прокси к backend: "
                    f"{type(e).__name__}: {e!s}. Проверьте uvicorn на 127.0.0.1:8000.",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8080), Handler)
    print("Frontend: http://127.0.0.1:8080")
    server.serve_forever()
