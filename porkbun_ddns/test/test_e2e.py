"""Hermetic end-to-end tests for the Porkbun DDNS client.

No real network traffic: the client talks to :class:`PorkbunAPIMock` on
127.0.0.1 and webhook delivery is captured by a second local HTTP server.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv6Address

import pytest

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import Config
from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.test.mock_porkbun_api import PorkbunAPIMock
from porkbun_ddns.webhook import fire_webhook

DOMAIN = "example.com"


class WebhookCaptureServer:
    """Captures POST bodies in a thread-safe list; status is configurable."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = []
        self.status = 200
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> WebhookCaptureServer:
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), _make_capture_handler(self))
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None


def _make_capture_handler(capture: WebhookCaptureServer) -> type[BaseHTTPRequestHandler]:
    """Build a handler that records POST bodies on the capture server."""
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            with capture._lock:
                capture.bodies.append(body)
            self.send_response(capture.status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args) -> None:  # silence default request logging
            pass

    return Handler


@pytest.fixture
def mock_api() -> PorkbunAPIMock:
    mock = PorkbunAPIMock(apikey="test-apikey", secretapikey="test-secret")
    mock.start()
    yield mock
    mock.stop()


@pytest.fixture
def webhook_capture() -> WebhookCaptureServer:
    server = WebhookCaptureServer()
    server.start()
    yield server
    server.stop()


def make_config(mock: PorkbunAPIMock,
                webhook_url: str = "",
                **overrides) -> Config:
    """Build a Config pointing at the mock, with overridable kwargs."""
    values = {
        "endpoint": f"{mock.url}/api/json/v3",
        "apikey": "test-apikey",
        "secretapikey": "test-secret",
        "webhook_url": webhook_url,
        "retry_count": "3",
        "retry_delay": "0",
    }
    values.update(overrides)
    return Config(**values)


def run_update(config: Config,
               public_ips: list[str],
               *,
               ipv4: bool = True,
               ipv6: bool = True) -> PorkbunDDNS:
    """Run one full update pass and return the client instance."""
    instance = PorkbunDDNS(
        config, DOMAIN, public_ips=public_ips, ipv4=ipv4, ipv6=ipv6)
    instance.update_records()
    return instance


def test_ipv4_creates_record_then_idempotent(mock_api):
    first = run_update(make_config(mock_api), ["203.0.113.5"],
                       ipv4=True, ipv6=False)
    assert len(first.changes) == 1
    assert len(mock_api.records["example.com"]) == 1
    record = mock_api.records["example.com"][0]
    assert record["type"] == "A"
    assert record["name"] == "example.com"
    assert record["content"] == "203.0.113.5"

    second = run_update(make_config(mock_api), ["203.0.113.5"],
                        ipv4=True, ipv6=False)
    assert second.changes == []
    assert len(mock_api.records["example.com"]) == 1
    assert mock_api.records["example.com"][0]["content"] == "203.0.113.5"


def test_ipv4_ip_change_triggers_delete_and_create(mock_api):
    run_update(make_config(mock_api), ["203.0.113.5"], ipv4=True, ipv6=False)

    updated = run_update(make_config(mock_api), ["203.0.113.9"],
                         ipv4=True, ipv6=False)
    assert len(updated.changes) == 1
    change = updated.changes[0]
    assert change["old_ip"] == "203.0.113.5"
    assert change["new_ip"] == "203.0.113.9"
    assert mock_api.records["example.com"][0]["content"] == "203.0.113.9"


def test_ipv6_aaaa_with_pinned_public_ips(mock_api):
    expected = IPv6Address("2001:db8::1").exploded
    first = run_update(make_config(mock_api), ["2001:db8::1"],
                       ipv4=False, ipv6=True)
    assert len(first.changes) == 1
    records = mock_api.records["example.com"]
    assert len(records) == 1
    assert records[0]["type"] == "AAAA"
    assert records[0]["content"] == expected

    second = run_update(make_config(mock_api), ["2001:db8::1"],
                        ipv4=False, ipv6=True)
    assert second.changes == []
    assert mock_api.records["example.com"][0]["content"] == expected


def test_retry_succeeds_after_transient_500s(mock_api):
    mock_api.fail_next = 2
    instance = run_update(make_config(mock_api, retry_count="3"),
                          ["203.0.113.5"], ipv4=True, ipv6=False)
    assert len(instance.changes) == 1
    assert len(mock_api.records["example.com"]) == 1
    # 3 retrieve attempts (2 x 500, 1 x 200) + create + post-create retrieve.
    assert mock_api.request_count == 5


def test_retry_gives_up_after_retry_count(mock_api):
    mock_api.fail_next = 5
    with pytest.raises(PorkbunDDNS_Error):
        run_update(make_config(mock_api, retry_count="3"),
                   ["203.0.113.5"], ipv4=True, ipv6=False)
    assert mock_api.request_count == 3


def test_invalid_api_keys_fail_fast(mock_api):
    with pytest.raises(PorkbunDDNS_Error, match="Invalid API Keys"):
        run_update(make_config(mock_api, apikey="wrong"),
                   ["203.0.113.5"], ipv4=True, ipv6=False)
    assert mock_api.request_count == 1


def test_webhook_sent_on_change_default_template(mock_api, webhook_capture):
    config = make_config(mock_api, webhook_url=webhook_capture.url)
    instance = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    assert fire_webhook(config, instance.changes, instance.domain)
    assert len(webhook_capture.bodies) == 1
    payload = json.loads(webhook_capture.bodies[0].decode("utf-8"))
    assert payload == {"text": "IP changed:  -> 203.0.113.5 (example.com)"}


def test_webhook_inline_template(mock_api, webhook_capture):
    config = make_config(
        mock_api,
        webhook_url=webhook_capture.url,
        webhook_template='{"msg": "{{ new_ips | join(", ") }} for {{ domain }}"}',
    )
    instance = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    assert fire_webhook(config, instance.changes, instance.domain)
    assert len(webhook_capture.bodies) == 1
    payload = json.loads(webhook_capture.bodies[0].decode("utf-8"))
    assert payload == {"msg": "203.0.113.5 for example.com"}


def test_webhook_template_file_precedence(mock_api, webhook_capture, tmp_path):
    template_file = tmp_path / "template.j2"
    template_file.write_text('{"from": "file", "domain": "{{ domain }}"}')
    config = make_config(
        mock_api,
        webhook_url=webhook_capture.url,
        webhook_template='{"from": "inline"}',
        webhook_template_file=str(template_file),
    )
    instance = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    assert fire_webhook(config, instance.changes, instance.domain)
    assert len(webhook_capture.bodies) == 1
    payload = json.loads(webhook_capture.bodies[0].decode("utf-8"))
    assert payload == {"from": "file", "domain": "example.com"}


def test_webhook_fire_and_forget_on_failure(mock_api, webhook_capture):
    webhook_capture.status = 500
    config = make_config(mock_api, webhook_url=webhook_capture.url)
    instance = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    # The webhook server's 500 must not propagate to the caller.
    assert fire_webhook(config, instance.changes, instance.domain)
    assert len(webhook_capture.bodies) == 1


def test_no_webhook_when_no_changes(mock_api, webhook_capture):
    config = make_config(mock_api, webhook_url=webhook_capture.url)
    first = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    assert fire_webhook(config, first.changes, first.domain)
    assert len(webhook_capture.bodies) == 1

    second = run_update(config, ["203.0.113.5"], ipv4=True, ipv6=False)
    assert second.changes == []
    assert not fire_webhook(config, second.changes, second.domain)
    assert len(webhook_capture.bodies) == 1
