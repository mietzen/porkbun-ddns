import json
import logging
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import Config
from porkbun_ddns.errors import PorkbunDDNS_Error

logger = logging.getLogger("porkbun_ddns")
logger.setLevel(logging.INFO)

valid_config = Config(
    endpoint="https://api.porkbun.com/api/json/v3",
    apikey="pk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    secretapikey="sk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
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

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
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
                      ]))
    def test_record_exists_and_up_to_date(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ["INFO:porkbun_ddns:A-Record of my-domain.local is up to date!",
                              "INFO:porkbun_ddns:AAAA-Record of my-domain.local is up to date!"])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
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
                      ]))
    def test_record_exists_and_out_dated(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
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

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api())
    def test_record_do_not_exists(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             [("INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS"),
                              ("INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS")])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
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
                      ]))
    def test_record_overwrite_alias_and_cname(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
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
        porkbun_ddns = PorkbunDDNS(valid_config, domain="example.com", ipv4=True, ipv6=False)

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
        porkbun_ddns = PorkbunDDNS(valid_config, domain="example.com", ipv4=False, ipv6=True)

        # Now when you call the method that uses urllib.request.urlopen(), it will get the mocked response
        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_public_ips()

        # Verify that the exception has the expected error message
        self.assertEqual(str(context.exception), "Failed to obtain IP Addresses!")


    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_api_network_unreachable(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = URLError(OSError(101, "Network is unreachable"))

        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)

        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_records()

        self.assertIn(
            "Error reaching https://api.porkbun.com/api/json/v3/dns/retrieve/my-domain.local! -",
            str(context.exception),
        )
        self.assertIn("Network is unreachable", str(context.exception))


class TestApiRetry(unittest.TestCase):

    def setUp(self):
        self.porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        self.url = valid_config.endpoint + "/dns/retrieve/" + domain

    @staticmethod
    def _success_response():
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"status": "SUCCESS"}).encode("utf-8")
        return mock_response

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_success_on_first_attempt(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = self._success_response()

        result = self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertEqual(result, {"status": "SUCCESS"})
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_success_after_retries(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            URLError(OSError(101, "Network is unreachable")),
            URLError(OSError(101, "Network is unreachable")),
            self._success_response(),
        ]

        with self.assertLogs("porkbun_ddns", level="WARNING") as cm:
            result = self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertEqual(result, {"status": "SUCCESS"})
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(len(cm.output), 2)
        self.assertTrue(all("Retrying in" in msg for msg in cm.output))

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_failure_after_all_retries(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            URLError(OSError(101, "Network is unreachable")),
            URLError(OSError(101, "Network is unreachable")),
            URLError(OSError(101, "Network is unreachable")),
        ]

        with self.assertRaises(PorkbunDDNS_Error) as context:
            self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertIn("Error reaching " + self.url + "!", str(context.exception))
        self.assertIn("Network is unreachable", str(context.exception))
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_http_400_raises_without_retry(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = HTTPError(self.url, 400, "Bad Request", None, None)

        with self.assertRaises(PorkbunDDNS_Error) as context:
            self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertEqual(str(context.exception), "Invalid API Keys!")
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_http_500_retries_then_raises(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            HTTPError(self.url, 500, "Internal Server Error", None, None),
            HTTPError(self.url, 500, "Internal Server Error", None, None),
            HTTPError(self.url, 500, "Internal Server Error", None, None),
        ]

        with self.assertRaises(PorkbunDDNS_Error) as context:
            self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertIn("HTTP 500", str(context.exception))
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_http_404_raises_without_retry(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = HTTPError(self.url, 404, "Not Found", None, None)

        with self.assertRaises(HTTPError):
            self.porkbun_ddns._api("/dns/retrieve/" + domain)

        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_retry_fields_not_sent_in_request_body(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = self._success_response()

        self.porkbun_ddns._api("/dns/retrieve/" + domain)

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("retry_count", body)
        self.assertNotIn("retry_delay", body)
        self.assertEqual(body["endpoint"], valid_config.endpoint)
        self.assertEqual(body["apikey"], valid_config.apikey)
        self.assertEqual(body["secretapikey"], valid_config.secretapikey)


if __name__ == "__main__":
    unittest.main()
