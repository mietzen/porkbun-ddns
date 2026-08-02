"""Network-dependent tests against the live Porkbun API and its spec.

These tests skip when the network is unreachable and are not part of the
hermetic suite. They keep the client's default endpoint and the mock honest.
"""

from __future__ import annotations

import json
import socket
import urllib.request

import pytest

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import DEFAULT_ENDPOINT, Config
from porkbun_ddns.test.mock_porkbun_api import PorkbunAPIMock

SPEC_URL = "https://porkbun.com/api/json/v3/spec"

DNS_ENDPOINTS = (
    "/dns/retrieve/{domain}",
    "/dns/create/{domain}",
    "/dns/delete/{domain}/{id}",
)


def _require_network() -> None:
    """Skip the test when the live API is unreachable."""
    try:
        socket.create_connection(("api.porkbun.com", 443), timeout=5)
    except OSError:
        pytest.skip("No network access; skipping live API tests")


def _fetch_spec() -> dict:
    with urllib.request.urlopen(SPEC_URL, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_200_schema(spec: dict, path: str) -> dict:
    """Extract the POST-200 response schema, resolving one level of $ref."""
    schema = spec["paths"][path]["post"]["responses"]["200"][
        "content"]["application/json"]["schema"]
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return spec["components"]["schemas"][name]
    return schema


def _schema_for_path(path: str, schemas: dict) -> dict | None:
    if "/dns/retrieve/" in path:
        return schemas["retrieve"]
    if "/dns/create/" in path:
        return schemas["create"]
    if "/dns/delete/" in path:
        return schemas["delete"]
    return None


def test_default_endpoint_reachable():
    _require_network()
    request = urllib.request.Request(
        DEFAULT_ENDPOINT + "/ping",
        data=json.dumps({}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.getcode() == 200
        body = json.loads(response.read().decode("utf-8"))
    assert body["status"] == "SUCCESS"


def test_mock_matches_spec():
    _require_network()
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - CI installs it
        pytest.skip("jsonschema not installed; skipping spec conformance test")

    spec = _fetch_spec()
    schemas = {
        endpoint.split("/")[2]: _resolve_200_schema(spec, endpoint)
        for endpoint in DNS_ENDPOINTS
    }

    mock = PorkbunAPIMock(apikey="test-apikey", secretapikey="test-secret")
    mock.start()
    try:
        mock.records["example.com"] = [
            {"id": "1", "name": "example.com", "type": "A",
             "content": "203.0.113.5", "ttl": "600"},
        ]
        config = Config(
            endpoint=f"{mock.url}/api/json/v3",
            apikey="test-apikey",
            secretapikey="test-secret",
            retry_count="3",
            retry_delay="0",
        )
        # One update pass with a changed IP drives retrieve, delete and create.
        PorkbunDDNS(
            config, "example.com", public_ips=["203.0.113.9"],
            ipv4=True, ipv6=False,
        ).update_records()
    finally:
        mock.stop()

    failures = []
    for path, status, body in mock.responses:
        schema = _schema_for_path(path, schemas)
        if schema is None:
            failures.append(f"no schema found for {path}")
            continue
        try:
            jsonschema.validate(body, schema)
        except jsonschema.ValidationError as err:
            failures.append(f"{path} ({status}): {err.message}")
    if failures:
        pytest.fail(
            "Mock responses do not conform to the live API spec:\n"
            + "\n".join(failures)
        )
