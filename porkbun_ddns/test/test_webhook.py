import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from urllib.error import URLError

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import AppConfig, Credentials, RetryPolicy, WebhookConfig
from porkbun_ddns.test.stubs import StubPorkbunAPIClient
from porkbun_ddns.test.test_porkbun_ddns import domain, ips, mock_api, valid_config
from porkbun_ddns.webhook import (
    DEFAULT_WEBHOOK_TEMPLATE,
    fire_webhook,
    render_webhook_payload,
)

logger = logging.getLogger("porkbun_ddns")
logger.setLevel(logging.INFO)

webhook_config = AppConfig(
    credentials=Credentials(
        apikey=valid_config.credentials.apikey,
        secretapikey=valid_config.credentials.secretapikey,
        endpoint=valid_config.credentials.endpoint,
    ),
    retry=RetryPolicy(),
    webhook=WebhookConfig(webhook_url="https://hooks.example.com/webhook"),
)

change = {"record_type": "A", "fqdn": domain, "old_ip": "127.0.0.2", "new_ip": "127.0.0.1"}


def mock_ok_response(status=200):
    mock_response = MagicMock()
    mock_response.getcode.return_value = status
    mock_response.__enter__.return_value = mock_response
    return mock_response


class TestWebhookFiring(unittest.TestCase):
    maxDiff = None

    def test_fires_on_change(self):
        mock_urlopen = MagicMock()
        mock_urlopen.return_value = mock_ok_response()
        fake = StubPorkbunAPIClient(records=mock_api(
            status="SUCCESS",
            mock_records=[
                {
                    "name": domain,
                    "type": "A",
                    "content": "127.0.0.2"},
                {
                    "name": domain,
                    "type": "AAAA",
                    "content": "0000:0000:0000:0000:0000:0000:0000:0002"},
            ])["records"])

        porkbun_ddns = PorkbunDDNS(webhook_config.credentials, webhook_config.retry, domain, ips,
                                   client=fake)
        porkbun_ddns.set_subdomain("@")
        porkbun_ddns.update_records()

        self.assertEqual(len(porkbun_ddns.changes), 2)
        self.assertTrue(fire_webhook(
            webhook_config.webhook, porkbun_ddns.changes, porkbun_ddns.domain,
            _urlopen=mock_urlopen))
        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 10)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("text", payload)
        self.assertIn("127.0.0.2", payload["text"])
        self.assertIn("127.0.0.1", payload["text"])

    def test_does_not_fire_when_up_to_date(self):
        mock_urlopen = MagicMock()
        fake = StubPorkbunAPIClient(records=mock_api(
            status="SUCCESS",
            mock_records=[
                {
                    "name": domain,
                    "type": "A",
                    "content": "127.0.0.1"},
                {
                    "name": domain,
                    "type": "AAAA",
                    "content": "0000:0000:0000:0000:0000:0000:0000:0001"},
            ])["records"])

        porkbun_ddns = PorkbunDDNS(webhook_config.credentials, webhook_config.retry, domain, ips,
                                   client=fake)
        porkbun_ddns.set_subdomain("@")
        porkbun_ddns.update_records()

        self.assertEqual(porkbun_ddns.changes, [])
        self.assertFalse(fire_webhook(
            webhook_config.webhook, porkbun_ddns.changes, porkbun_ddns.domain,
            _urlopen=mock_urlopen))
        mock_urlopen.assert_not_called()

    def test_does_not_fire_without_url(self):
        mock_urlopen = MagicMock()
        self.assertFalse(fire_webhook(valid_config.webhook, [change], domain,
                                      _urlopen=mock_urlopen))
        mock_urlopen.assert_not_called()

    def test_does_not_fire_without_changes(self):
        mock_urlopen = MagicMock()
        self.assertFalse(fire_webhook(webhook_config.webhook, [], domain,
                                      _urlopen=mock_urlopen))
        mock_urlopen.assert_not_called()

    def test_aggregates_across_subdomains(self):
        mock_urlopen = MagicMock()
        mock_urlopen.return_value = mock_ok_response()
        config = AppConfig(
            credentials=Credentials(
                apikey=valid_config.credentials.apikey,
                secretapikey=valid_config.credentials.secretapikey,
                endpoint=valid_config.credentials.endpoint,
            ),
            retry=RetryPolicy(),
            webhook=WebhookConfig(
                webhook_url="https://hooks.example.com/webhook",
                webhook_template='{"text": "{{ changes | length }} changes for {{ domain }}"}',
            ),
        )
        fake = StubPorkbunAPIClient(records=mock_api()["records"])

        porkbun_ddns = PorkbunDDNS(config.credentials, config.retry, domain, ["127.0.0.1"],
                                   client=fake)
        for subdomain in ["www", "api"]:
            porkbun_ddns.set_subdomain(subdomain)
            porkbun_ddns.update_records()

        self.assertEqual(len(porkbun_ddns.changes), 2)
        self.assertTrue(fire_webhook(config.webhook, porkbun_ddns.changes, porkbun_ddns.domain,
                                     _urlopen=mock_urlopen))
        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["text"], "2 changes for my-domain.local")

    def test_failure_does_not_crash(self):
        mock_urlopen = MagicMock()
        mock_urlopen.side_effect = URLError(OSError(101, "Network is unreachable"))
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            self.assertTrue(fire_webhook(webhook_config.webhook, [change], domain,
                                         _urlopen=mock_urlopen))
        mock_urlopen.assert_called_once()

    def test_timeout_does_not_crash(self):
        mock_urlopen = MagicMock()
        mock_urlopen.side_effect = TimeoutError("timed out")
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            self.assertTrue(fire_webhook(webhook_config.webhook, [change], domain,
                                         _urlopen=mock_urlopen))

    def test_non_2xx_logs_warning(self):
        mock_urlopen = MagicMock()
        mock_urlopen.return_value = mock_ok_response(status=500)
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            self.assertTrue(fire_webhook(webhook_config.webhook, [change], domain,
                                         _urlopen=mock_urlopen))

    def test_webhook_fields_excluded_from_api_payload(self):
        porkbun_ddns = PorkbunDDNS(webhook_config.credentials, webhook_config.retry, domain, ips)
        body = porkbun_ddns.credentials._asdict()
        self.assertNotIn("webhook_url", body)
        self.assertNotIn("webhook_template", body)
        self.assertNotIn("webhook_template_file", body)


class TestWebhookRendering(unittest.TestCase):
    maxDiff = None

    def test_default_template_renders_valid_json(self):
        payload = render_webhook_payload([change], domain)
        parsed = json.loads(payload)
        self.assertIn("text", parsed)
        self.assertIn("127.0.0.2", parsed["text"])
        self.assertIn("127.0.0.1", parsed["text"])
        self.assertIn(domain, parsed["text"])

    def test_default_template_renders_with_empty_old_ips(self):
        payload = render_webhook_payload(
            [{"record_type": "A", "fqdn": domain, "old_ip": None, "new_ip": "127.0.0.1"}],
            domain,
        )
        parsed = json.loads(payload)
        self.assertIn("127.0.0.1", parsed["text"])

    def test_inline_template_takes_precedence_over_default(self):
        payload = render_webhook_payload(
            [change], domain, template='{"from": "inline"}')
        self.assertEqual(json.loads(payload), {"from": "inline"})

    def test_file_template_takes_precedence_over_inline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = Path(tmpdir) / "template.j2"
            template_file.write_text('{"from": "file"}')
            payload = render_webhook_payload(
                [change],
                domain,
                template='{"from": "inline"}',
                template_file=str(template_file),
            )
        self.assertEqual(json.loads(payload), {"from": "file"})

    def test_missing_file_falls_back_to_inline(self):
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            payload = render_webhook_payload(
                [change],
                domain,
                template='{"from": "inline"}',
                template_file="/nonexistent/template.j2",
            )
        self.assertEqual(json.loads(payload), {"from": "inline"})

    def test_missing_file_falls_back_to_default(self):
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            payload = render_webhook_payload(
                [change], domain, template_file="/nonexistent/template.j2")
        self.assertEqual(json.loads(payload), json.loads(
            render_webhook_payload([change], domain, template=DEFAULT_WEBHOOK_TEMPLATE)))

    def test_invalid_template_falls_back_to_default(self):
        with self.assertLogs("porkbun_ddns", level="WARNING"):
            payload = render_webhook_payload(
                [change], domain, template="{{ old_ips | join(")
        self.assertEqual(json.loads(payload), json.loads(
            render_webhook_payload([change], domain, template=DEFAULT_WEBHOOK_TEMPLATE)))

    def test_context_has_unique_ips_and_timestamp(self):
        changes = [
            {"record_type": "A", "fqdn": domain, "old_ip": "127.0.0.2", "new_ip": "127.0.0.1"},
            {"record_type": "AAAA", "fqdn": domain, "old_ip": "127.0.0.2", "new_ip": "2001:db8::1"},
        ]
        payload = render_webhook_payload(changes, domain, template='{{ changes | length }}|{{ old_ips | length }}|{{ new_ips | length }}|{{ timestamp }}')
        count, old_count, new_count, timestamp = payload.split("|")
        self.assertEqual(count, "2")
        self.assertEqual(old_count, "1")
        self.assertEqual(new_count, "2")
        self.assertTrue(timestamp.endswith(("+00:00", "Z")))


if __name__ == "__main__":
    unittest.main()
