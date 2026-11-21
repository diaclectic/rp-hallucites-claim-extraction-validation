import json
import sys
import traceback
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse

Route = Callable[[dict, str], "dict | list | tuple[str, bytes]"]


class RequestHandler(BaseHTTPRequestHandler):
    """Serves the static pages and calls a route for each API request.

    A route is `route(body, arg)`. `body` is the parsed JSON of a POST, and `arg` is the last path
    segment for a route registered as `"GET /api/eml/*"`. It returns a dict or list, sent as JSON, or
    a `(content_type, bytes)` tuple. A `ValueError` becomes a 400 and a `LookupError` a 404.
    """

    MAX_BODY = 20 * 1024 * 1024
    HOSTS = ("127.0.0.1", "localhost")

    def __init__(self, *args: object, routes: dict[str, Route], static_dir: Path, page: str, **kwargs: object) -> None:
        self.routes = routes
        self.static_dir = static_dir
        self.page = page
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def log_message(self, format: str, *args: object) -> None:
        """Silence the per-request log lines, which would bury the tool's own output."""

    def _handle(self, method: str) -> None:
        port = self.server.server_address[1]
        if self.headers.get("Host", "").rsplit(":", 1)[0] not in self.HOSTS:
            return self._send_json(403, {"error": "Unexpected Host header"})
        allowed = {f"http://{host}:{port}" for host in self.HOSTS}
        origin = self.headers.get("Origin")
        if method == "POST" and origin is not None and origin not in allowed:
            return self._send_json(403, {"error": "Unexpected Origin header"})
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                route, arg = self._find_route(method, path)
                if route is None:
                    return self._send_json(404, {"error": f"No route for {method} {path}"})
                result = route(self._read_body(), arg)
                if isinstance(result, tuple):
                    return self._send(200, *result)
                return self._send_json(200, result)
            if method == "GET":
                return self._send_static(path)
            return self._send_json(404, {"error": "Not found"})
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except LookupError as error:
            self._send_json(404, {"error": f"Not found: {error}"})
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            self._send_json(500, {"error": f"Internal error: {error}"})

    def _find_route(self, method: str, path: str) -> tuple[Route | None, str]:
        if f"{method} {path}" in self.routes:
            return self.routes[f"{method} {path}"], ""
        prefix, _, arg = path.rpartition("/")
        return self.routes.get(f"{method} {prefix}/*"), unquote(arg)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > self.MAX_BODY:
            raise ValueError("Request body is too large")
        if not length:
            return {}
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ValueError(f"Request body is not valid JSON: {error}") from error
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object")
        return body

    def _send_static(self, path: str) -> None:
        name = self.page if path == "/" else unquote(path).lstrip("/")
        file = (self.static_dir / name).resolve()
        if not file.is_relative_to(self.static_dir.resolve()) or not file.is_file():
            return self._send_json(404, {"error": "Not found"})
        content_types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
        self._send(
            200, f"{content_types.get(file.suffix, 'application/octet-stream')}; charset=utf-8", file.read_bytes()
        )

    def _send_json(self, status: int, payload: dict | list) -> None:
        self._send(status, "application/json", json.dumps(payload).encode())

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
