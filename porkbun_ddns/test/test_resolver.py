from __future__ import annotations

import unittest
from ipaddress import IPv4Address, IPv6Address
from unittest.mock import MagicMock

from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.resolver import PublicIPResolver


def make_urlopen(*code_body) -> callable:
    """Build a fake _urlopen returning responses in order.

    Each pair of args is a (status_code, body_text) response. The resolver
    walks the provider URLs in order until one returns a 200.
    """
    responses = list(zip(code_body[0::2], code_body[1::2]))

    def _urlopen(url, timeout=30):
        code, body = responses.pop(0)
        response = MagicMock()
        response.getcode.return_value = code
        response.read.return_value = body.encode("utf-8")
        return response

    return _urlopen


class TestPublicIPResolver(unittest.TestCase):

    def test_ipv4_only(self):
        resolver = PublicIPResolver(
            ipv4=True, ipv6=False, _urlopen=make_urlopen(200, "1.2.3.4"))
        self.assertEqual(resolver.resolve(), [IPv4Address("1.2.3.4")])

    def test_ipv6_only(self):
        resolver = PublicIPResolver(
            ipv4=False, ipv6=True, _urlopen=make_urlopen(200, "2001:db8::1"))
        self.assertEqual(resolver.resolve(), [IPv6Address("2001:db8::1")])

    def test_both_families(self):
        resolver = PublicIPResolver(
            ipv4=True, ipv6=True,
            _urlopen=make_urlopen(200, "1.2.3.4", 200, "2001:db8::1"))
        self.assertEqual(
            set(resolver.resolve()),
            {IPv4Address("1.2.3.4"), IPv6Address("2001:db8::1")})

    def test_first_provider_fails_then_second_wins(self):
        resolver = PublicIPResolver(
            ipv4=True, ipv6=False,
            _urlopen=make_urlopen(500, "", 200, "1.2.3.4"))
        self.assertEqual(resolver.resolve(), [IPv4Address("1.2.3.4")])

    def test_all_providers_fail_raises(self):
        resolver = PublicIPResolver(
            ipv4=True, ipv6=False,
            _urlopen=make_urlopen(500, "", 500, "", 500, ""))
        with self.assertRaises(PorkbunDDNS_Error) as context:
            resolver.resolve()
        self.assertEqual(str(context.exception), "Failed to obtain IP Addresses!")

    def test_urlopen_error_falls_through_to_next_provider(self):
        def flaky(url, timeout=30):
            if url.endswith("v4.ident.me"):
                raise __import__("urllib.error").error.URLError(
                    OSError(101, "Network is unreachable"))
            response = MagicMock()
            response.getcode.return_value = 200
            response.read.return_value = b"1.2.3.4"
            return response

        resolver = PublicIPResolver(ipv4=True, ipv6=False, _urlopen=flaky)
        self.assertEqual(resolver.resolve(), [IPv4Address("1.2.3.4")])

    def test_static_ips_override(self):
        resolver = PublicIPResolver()
        self.assertEqual(resolver.resolve(["1.2.3.4"]), [IPv4Address("1.2.3.4")])

    def test_static_ips_dedup_and_unspecified_filtered(self):
        resolver = PublicIPResolver()
        self.assertEqual(
            resolver.resolve(["1.2.3.4", "1.2.3.4", "0.0.0.0"]),
            [IPv4Address("1.2.3.4")])

    def test_no_sources_raises(self):
        resolver = PublicIPResolver(ipv4=False, ipv6=False, _urlopen=make_urlopen())
        with self.assertRaises(PorkbunDDNS_Error):
            resolver.resolve()


if __name__ == "__main__":
    unittest.main()