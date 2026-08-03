"""A hermetic, stdlib-only fake of the Porkbun JSON API v3.

Covers exactly the three DNS endpoints the client calls (retrieve, create,
delete) plus the authentication and fault-injection behaviour needed to
exercise the client's retry and error handling end-to-end. Response shapes
follow the official OpenAPI spec at https://porkbun.com/api/json/v3/spec.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


def _make_handler(mock: PorkbunAPIMock) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to a specific mock instance."""
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            mock._handle(self)

        def log_message(self, *args) -> None:  # silence default request logging
            pass

    return Handler


class PorkbunAPIMock:
    """In-process fake of the Porkbun JSON API v3.

    Records are stored per domain in ``records`` (domain -> list of record
    dicts). ``fail_next`` makes the next request fail with HTTP 500, and
    ``request_count`` counts every request received. Every request body is
    recorded in ``request_bodies`` and every response sent is recorded as
    ``(path, status, body)`` in ``responses``.
    """

    def __init__(self, apikey: str, secretapikey: str) -> None:
        self.apikey = apikey
        self.secretapikey = secretapikey
        self.records: dict[str, list[dict]] = {}
        self.fail_next = 0
        self.request_count = 0
        self.responses: list[tuple[str, int, dict | None]] = []
        self.request_bodies: list[dict] = []
        self._next_id = 1
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Base URL of the mock, e.g. ``http://127.0.0.1:53421``."""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self, host: str = "127.0.0.1", port: int = 0) -> PorkbunAPIMock:
        """Bind a host/port (ephemeral by default) and serve on a daemon thread."""
        self._server = ThreadingHTTPServer((host, port), _make_handler(self))
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def serve_forever(self) -> None:
        """Serve requests on the current thread until ``stop`` is called.

        Blocking; used by the standalone ``__main__`` runner (docker sidecar).
        """
        if self._server:
            self._server.serve_forever()

    def stop(self) -> None:
        """Shut the server down and free the port."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        self.request_count += 1
        # Fault injection applies to any request, including auth checks.
        if self.fail_next > 0:
            self.fail_next -= 1
            self._respond(handler, 500, b"")
            return
        try:
            length = int(handler.headers.get("Content-Length", 0))
            raw = handler.rfile.read(length) if length else b""
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, json.JSONDecodeError):
            self._respond(handler, 400,
                          {"status": "ERROR", "message": "Invalid JSON"})
            return
        self.request_bodies.append(body)
        if (body.get("apikey") != self.apikey
                or body.get("secretapikey") != self.secretapikey):
            self._respond(handler, 400,
                          {"status": "ERROR", "message": "Invalid API Keys"})
            return
        action, domain, record_id = self._route(handler.path)
        if action == "retrieve" and domain is not None and record_id is None:
            self._respond(handler, 200, {
                "status": "SUCCESS",
                "records": list(self.records.get(domain, [])),
            })
        elif action == "create" and domain is not None and record_id is None:
            record = self._create_record(domain, body)
            self._respond(handler, 200,
                          {"status": "SUCCESS", "id": record["id"]})
        elif action == "delete" and domain is not None and record_id is not None:
            self._delete_record(domain, record_id)
            self._respond(handler, 200, {"status": "SUCCESS"})
        else:
            self._respond(handler, 404,
                          {"status": "ERROR", "message": "Not found"})

    @staticmethod
    def _route(path: str) -> tuple[str | None, str | None, str | None]:
        """Split a request path into ``(action, domain, record_id)``.

        Expects ``/api/json/v3/dns/<action>/<domain>[/<id>]``.
        """
        parts = path.split("?", 1)[0].strip("/").split("/")
        if len(parts) >= 5 and parts[:4] == ["api", "json", "v3", "dns"]:
            action = unquote(parts[4])
            domain = unquote(parts[5]) if len(parts) > 5 else None
            record_id = unquote(parts[6]) if len(parts) > 6 else None
            return action, domain, record_id
        return None, None, None

    def _create_record(self, domain: str, body: dict) -> dict:
        """Store a record, mapping the client's ``name`` to the fqdn.

        The real API stores and returns the fully-qualified record name: a
        body ``name`` of ``"@"`` means the domain itself, anything else is
        joined to the domain. ``ttl`` is stored as a string, matching what
        the real API returns.
        """
        name = body.get("name", "@")
        fqdn = domain if name == "@" else f"{name}.{domain}"
        record = {
            key: value
            for key, value in body.items()
            if key not in ("apikey", "secretapikey", "endpoint", "name")
        }
        record["id"] = str(self._next_id)
        record["name"] = fqdn
        record["ttl"] = str(record.get("ttl", 600))
        self._next_id += 1
        self.records.setdefault(domain, []).append(record)
        return record

    def _delete_record(self, domain: str, record_id: str) -> None:
        self.records[domain] = [
            record for record in self.records.get(domain, [])
            if record["id"] != record_id
        ]

    def _respond(self, handler: BaseHTTPRequestHandler, status: int,
                 payload: dict | bytes) -> None:
        if isinstance(payload, dict):
            body_bytes = json.dumps(payload).encode("utf-8")
            content_type = "application/json"
            recorded: dict | None = payload
        else:
            body_bytes = payload
            content_type = None
            recorded = None
        self.responses.append((handler.path, status, recorded))
        handler.send_response(status)
        if content_type:
            handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body_bytes)))
        handler.end_headers()
        handler.wfile.write(body_bytes)


if __name__ == "__main__":
    import os

    mock = PorkbunAPIMock(
        apikey=os.getenv("APIKEY", "test-apikey"),
        secretapikey=os.getenv("SECRETAPIKEY", "test-secret"),
    )
    mock.start(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
    print(f"Mock Porkbun API listening on {mock.url}", flush=True)
    try:
        mock.serve_forever()
    except KeyboardInterrupt:
        mock.stop()
