import logging
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.api import PorkbunAPIClient
from porkbun_ddns.config import AppConfig, Credentials, RetryPolicy, WebhookConfig
from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.test.fakes import FakePorkbunAPIClient
from porkbun_ddns.test.mock_porkbun_api import PorkbunAPIMock

logger = logging.getLogger("porkbun_ddns")
logger.setLevel(logging.INFO)

valid_config = AppConfig(
    credentials=Credentials(
        apikey="pk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        secretapikey="sk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        endpoint="https://api.porkbun.com/api/json/v3",
    ),
    retry=RetryPolicy(),
    webhook=WebhookConfig(),
)

domain = "my-domain.local"
ips = ["127.0.0.1", "::1"]


def mock_api(status="SUCCESS", mock_records=None):
    records = []
    if mock_records:
        mock_id = 1111111111
        for record in mock_records:
            records.append(
                {
                    "id": str(mock_id),
                    "name": record["name"],
                    "type": record["type"],
                    "content": record["content"],
                    "ttl": "600",
                    "prio": "0",
                    "notes": "",
                },
            )
            mock_id += 1
    return {"status": status, "records": records}


class TestPorkbunDDNS(unittest.TestCase):
    maxDiff = None

    def test_record_exists_and_up_to_date(self):
        fake = FakePorkbunAPIClient(records=mock_api(
            status="SUCCESS",
            mock_records=[
                {
                    "name": "my-domain.local",
                    "type": "A",
                    "content": "127.0.0.1"},
                {
                    "name": "my-domain.local",
                    "type": "AAAA",
                    "content": "0000:0000:0000:0000:0000:0000:0000:0001"},
            ])["records"])
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain, ips,
                                   client=fake)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ["INFO:porkbun_ddns:A-Record of my-domain.local is up to date!",
                              "INFO:porkbun_ddns:AAAA-Record of my-domain.local is up to date!"])

    def test_record_exists_and_out_dated(self):
        fake = FakePorkbunAPIClient(records=mock_api(
            status="SUCCESS",
            mock_records=[
                {
                    "name": "my-domain.local",
                    "type": "A",
                    "content": "127.0.0.2"},
                {
                    "name": "my-domain.local",
                    "type": "AAAA",
                    "content": "0000:0000:0000:0000:0000:0000:0000:0002"},
            ])["records"])
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain, ips,
                                   client=fake)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             [("INFO:porkbun_ddns:Deleting A-Record for my-domain.local with content: "
                              "127.0.0.2, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Deleting AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0002, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS")])

    def test_record_do_not_exists(self):
        fake = FakePorkbunAPIClient(records=mock_api()["records"])
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain, ips,
                                   client=fake)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             [("INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS")])

    def test_record_overwrite_alias_and_cname(self):
        fake = FakePorkbunAPIClient(records=mock_api(
            status="SUCCESS",
            mock_records=[
                {
                    "name": "my-domain.local",
                    "type": "ALIAS",
                    "content": "my-domain.lan",
                },
                {
                    "name": "my-domain.local",
                    "type": "CNAME",
                    "content": "my-domain.lan"},
            ])["records"])
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain, ips,
                                   client=fake)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             [("INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS")])

    @patch("urllib.request.urlopen")
    def test_urlopen_returns_500_ipv4(self, mock_urlopen):
        # Set up the mock to return a response with status code 500
        mock_response = MagicMock()
        mock_response.getcode.return_value = 500
        mock_urlopen.return_value = mock_response

        # Instantiate your class or call the method that uses urllib.request.urlopen()
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain="example.com", ipv4=True, ipv6=False)

        # Now when you call the method that uses urllib.request.urlopen(), it will get the mocked response
        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_public_ips()

        # Verify that the exception has the expected error message
        self.assertEqual(str(context.exception), "Failed to obtain IP Addresses!")

    @patch("urllib.request.urlopen")
    def test_urlopen_returns_500_ipv6(self, mock_urlopen):
        # Set up the mock to return a response with status code 500
        mock_response = MagicMock()
        mock_response.getcode.return_value = 500
        mock_urlopen.return_value = mock_response

        # Instantiate your class or call the method that uses urllib.request.urlopen()
        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain="example.com", ipv4=False, ipv6=True)

        # Now when you call the method that uses urllib.request.urlopen(), it will get the mocked response
        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_public_ips()

        # Verify that the exception has the expected error message
        self.assertEqual(str(context.exception), "Failed to obtain IP Addresses!")


    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_api_network_unreachable(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = URLError(OSError(101, "Network is unreachable"))

        porkbun_ddns = PorkbunDDNS(valid_config.credentials, valid_config.retry, domain, ips)

        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_records()

        self.assertIn(
            "Error reaching https://api.porkbun.com/api/json/v3/dns/retrieve/my-domain.local! -",
            str(context.exception),
        )
        self.assertIn("Network is unreachable", str(context.exception))


class TestApiRetry(unittest.TestCase):

    def setUp(self):
        self.mock = PorkbunAPIMock(apikey="test-apikey", secretapikey="test-secret")
        self.mock.start()
        self.credentials = Credentials(
            apikey="test-apikey",
            secretapikey="test-secret",
            endpoint=f"{self.mock.url}/api/json/v3",
        )
        self.retry = RetryPolicy(retry_count=3, retry_delay=0)
        self.client = PorkbunAPIClient(self.credentials, self.retry)

    def tearDown(self):
        self.mock.stop()

    def test_success_on_first_attempt(self):
        result = self.client.retrieve_records(domain)

        self.assertEqual(result, [])
        self.assertEqual(self.mock.request_count, 1)

    def test_success_after_retries(self):
        self.mock.fail_next = 2

        with self.assertLogs("porkbun_ddns", level="WARNING") as cm:
            result = self.client.retrieve_records(domain)

        self.assertEqual(result, [])
        self.assertEqual(self.mock.request_count, 3)
        self.assertEqual(len(cm.output), 2)
        self.assertTrue(all("Retrying in" in msg for msg in cm.output))

    def test_failure_after_all_retries(self):
        self.mock.fail_next = 3

        with self.assertRaises(PorkbunDDNS_Error) as context:
            self.client.retrieve_records(domain)

        self.assertIn("Error reaching", str(context.exception))
        self.assertIn("HTTP 500", str(context.exception))
        self.assertEqual(self.mock.request_count, 3)

    def test_http_400_raises_without_retry(self):
        bad_client = PorkbunAPIClient(
            Credentials(apikey="wrong", secretapikey="test-secret",
                        endpoint=self.credentials.endpoint),
            self.retry,
        )

        with self.assertRaises(PorkbunDDNS_Error) as context:
            bad_client.retrieve_records(domain)

        self.assertEqual(str(context.exception), "Invalid API Keys!")
        self.assertEqual(self.mock.request_count, 1)

    def test_http_500_retries_then_raises(self):
        self.mock.fail_next = 3

        with self.assertRaises(PorkbunDDNS_Error) as context:
            self.client.retrieve_records(domain)

        self.assertIn("HTTP 500", str(context.exception))
        self.assertEqual(self.mock.request_count, 3)

    def test_http_404_raises_without_retry(self):
        with self.assertRaises(HTTPError):
            self.client._post(
                "/dns/retrieve/" + domain + "/extra",
                {"apikey": "test-apikey", "secretapikey": "test-secret"},
            )

        self.assertEqual(self.mock.request_count, 1)

    def test_retry_fields_not_sent_in_request_body(self):
        self.client.retrieve_records(domain)

        body = self.mock.request_bodies[0]
        self.assertNotIn("retry_count", body)
        self.assertNotIn("retry_delay", body)
        self.assertEqual(body["endpoint"], self.credentials.endpoint)
        self.assertEqual(body["apikey"], self.credentials.apikey)
        self.assertEqual(body["secretapikey"], self.credentials.secretapikey)


if __name__ == "__main__":
    unittest.main()
