import logging
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from porkbun_ddns.config import Config
from porkbun_ddns import PorkbunDDNS
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
    records = list()
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
                             ["INFO:porkbun_ddns:Deleting A-Record for my-domain.local with content: "
                              "127.0.0.2, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS",
                              "INFO:porkbun_ddns:Deleting AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0002, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS"])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api())
    def test_record_do_not_exists(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs("porkbun_ddns", level="INFO") as cm:
            porkbun_ddns.set_subdomain("@")
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ["INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS"])

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
                             ["INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS",
                              "INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: "
                              "127.0.0.1, Status: SUCCESS",
                              "INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS",
                              "INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: "
                              "my-domain.lan, Status: SUCCESS",
                              "INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: "
                              "0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS"])

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


    @patch("urllib.request.urlopen")
    def test_api_network_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = URLError(OSError(101, "Network is unreachable"))

        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)

        with self.assertRaises(PorkbunDDNS_Error) as context:
            porkbun_ddns.get_records()

        self.assertIn(
            "Error reaching https://api.porkbun.com/api/json/v3/dns/retrieve/my-domain.local! -",
            str(context.exception),
        )
        self.assertIn("Network is unreachable", str(context.exception))

if __name__ == "__main__":
    unittest.main()
