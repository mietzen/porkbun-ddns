import unittest
from ipaddress import IPv4Address, IPv6Address

from porkbun_ddns.reconcile import Ensure, reconcile

FQDN = "example.com"


class TestReconcile(unittest.TestCase):
    maxDiff = None

    def test_dual_ipv4_with_existing_aaaa_creates_both(self):
        # Regression: with a frozen snapshot containing only an AAAA record,
        # two desired v4 IPs must BOTH be created (never delete the first
        # created A record in favour of the second).
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "AAAA",
                  "content": "2001:db8::1", "id": "r1"}],
                [IPv4Address("1.2.3.4"), IPv4Address("5.6.7.8")],
                FQDN,
            ),
            [
                Ensure("A", FQDN, "1.2.3.4", None),
                Ensure("A", FQDN, "5.6.7.8", None),
            ],
        )

    def test_up_to_date_emits_nothing(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "A",
                  "content": "1.2.3.4", "id": "r1"}],
                [IPv4Address("1.2.3.4")],
                FQDN,
            ),
            [],
        )

    def test_replace_existing_a_with_new_content(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "A",
                  "content": "1.2.3.4", "id": "r1"}],
                [IPv4Address("5.6.7.8")],
                FQDN,
            ),
            [Ensure("A", FQDN, "5.6.7.8", "r1")],
        )

    def test_overwrite_alias(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "ALIAS",
                  "content": "example.lan", "id": "r1"}],
                [IPv4Address("1.2.3.4")],
                FQDN,
            ),
            [Ensure("A", FQDN, "1.2.3.4", "r1")],
        )

    def test_overwrite_alias_and_cname(self):
        self.assertEqual(
            reconcile(
                [
                    {"name": FQDN, "type": "ALIAS",
                     "content": "a.lan", "id": "r1"},
                    {"name": FQDN, "type": "CNAME",
                     "content": "b.lan", "id": "r2"},
                ],
                [IPv4Address("1.2.3.4")],
                FQDN,
            ),
            [
                Ensure("A", FQDN, "1.2.3.4", "r1"),
                Ensure("A", FQDN, "1.2.3.4", "r2"),
            ],
        )

    def test_create_missing_when_fqdn_has_aaaa_only(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "AAAA",
                  "content": "2001:db8::1", "id": "r1"}],
                [IPv4Address("1.2.3.4")],
                FQDN,
            ),
            [Ensure("A", FQDN, "1.2.3.4", None)],
        )

    def test_create_new_when_fqdn_absent(self):
        self.assertEqual(
            reconcile(
                [{"name": "other.com", "type": "A",
                  "content": "1.2.3.4", "id": "r1"}],
                [IPv4Address("5.6.7.8")],
                FQDN,
            ),
            [Ensure("A", FQDN, "5.6.7.8", None)],
        )

    def test_create_aaaa_when_fqdn_has_a_only(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "A",
                  "content": "1.2.3.4", "id": "r1"}],
                [IPv6Address("2001:db8::1")],
                FQDN,
            ),
            [Ensure("AAAA", FQDN, IPv6Address("2001:db8::1").exploded, None)],
        )

    def test_mixed_up_to_date_and_missing(self):
        self.assertEqual(
            reconcile(
                [{"name": FQDN, "type": "A",
                  "content": "1.2.3.4", "id": "r1"}],
                [IPv4Address("1.2.3.4"), IPv4Address("5.6.7.8")],
                FQDN,
            ),
            [Ensure("A", FQDN, "5.6.7.8", "r1")],
        )


if __name__ == "__main__":
    unittest.main()
