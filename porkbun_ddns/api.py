"""Deep client for the Porkbun JSON API v3 DNS endpoints."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from urllib.error import HTTPError, URLError

from porkbun_ddns.config import Credentials, RetryPolicy
from porkbun_ddns.errors import PorkbunDDNS_Error

logger = logging.getLogger("porkbun_ddns")


class PorkbunAPIClient:
    """Typed transport for the Porkbun JSON API v3.

    Owns authentication, HTTP transport and the retry loop. ``retrieve_records``
    raises on non-SUCCESS responses; ``create_record`` and ``delete_record``
    return the status string for logging without raising.
    """

    def __init__(self, credentials: Credentials, retry: RetryPolicy) -> None:
        self.credentials = credentials
        self.retry = retry

    def retrieve_records(self, domain: str) -> list[dict]:
        """Retrieve the DNS records for the given domain.

        Raises ``PorkbunDDNS_Error`` when the API does not report SUCCESS.
        """
        response = self._post("/dns/retrieve/" + domain, self._auth_body())
        if response["status"] != "SUCCESS":
            raise PorkbunDDNS_Error(
                "Failed to get records.\n" +
                f"Make sure you specified the correct domain ({domain}),\n" +
                "and that API access has been enabled for this domain.",
            )
        return response["records"]

    def create_record(self, domain: str, name: str, record_type: str,
                      content: str, ttl: int = 600) -> str:
        """Create a DNS record; returns the status string for logging."""
        body = self._auth_body()
        body.update({"name": name, "type": record_type,
                     "content": content, "ttl": ttl})
        return self._post("/dns/create/" + domain, body)["status"]

    def delete_record(self, domain: str, record_id: str) -> str:
        """Delete a DNS record; returns the status string for logging."""
        return self._post(
            "/dns/delete/" + domain + "/" + record_id, self._auth_body())["status"]

    def _auth_body(self) -> dict:
        return self.credentials._asdict()

    def _post(self, target: str, data: dict) -> dict:
        """Send a POST request, retrying transient failures.

        Transient failures (unreachable endpoint, timeouts, HTTP 5xx) are
        retried up to ``retry.retry_count`` times, waiting ``retry.retry_delay``
        seconds between attempts, before a ``PorkbunDDNS_Error`` is raised.
        HTTP 400 is treated as invalid API keys and raises immediately.
        """
        req = urllib.request.Request(self.credentials.endpoint + target)
        req.data = json.dumps(data).encode("utf8")
        for attempt in range(self.retry.retry_count):
            try:
                response = urllib.request.urlopen(req, timeout=30).read()
                return json.loads(response.decode("utf-8"))
            except HTTPError as err:
                if err.code == 400:
                    raise PorkbunDDNS_Error("Invalid API Keys!")
                if err.code < 500:
                    raise
                error_message = f"Error reaching {req.get_full_url()}! - HTTP {err.code}"
            except URLError as err:
                error_message = f"Error reaching {req.get_full_url()}! - {err.reason}"
            if attempt < self.retry.retry_count - 1:
                logger.warning(
                    "%s Retrying in %s seconds (attempt %s/%s).",
                    error_message, self.retry.retry_delay, attempt + 1,
                    self.retry.retry_count)
                time.sleep(self.retry.retry_delay)
            else:
                raise PorkbunDDNS_Error(error_message)
