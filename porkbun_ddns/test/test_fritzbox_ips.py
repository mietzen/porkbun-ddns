from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import call, patch

from porkbun_ddns.scripts import fritzbox_ips


def run_script(argv: list[str], side_effect) -> tuple[int, str]:
    """Run ``fritzbox_ips.main`` with a stubbed helper and captured stdout."""
    with patch("porkbun_ddns.scripts.fritzbox_ips.get_ips_from_fritzbox",
               side_effect=side_effect) as mock, \
            contextlib.redirect_stdout(io.StringIO()) as out:
        code = fritzbox_ips.main(argv)
    return code, out.getvalue(), mock


class TestFritzboxIpsScript(unittest.TestCase):

    def test_default_queries_both_families(self):
        code, output, mock = run_script(
            ["192.168.1.1"], ["1.2.3.4", "2001:db8::1"])
        self.assertEqual(code, 0)
        self.assertEqual(mock.call_args_list, [
            call("192.168.1.1", ip_version=4),
            call("192.168.1.1", ip_version=6),
        ])
        self.assertEqual(output, "1.2.3.4\n2001:db8::1\n")

    def test_v4_flag_queries_only_ipv4(self):
        code, output, mock = run_script(["192.168.1.1", "--v4"], ["1.2.3.4"])
        self.assertEqual(code, 0)
        mock.assert_called_once_with("192.168.1.1", ip_version=4)
        self.assertEqual(output, "1.2.3.4\n")

    def test_v6_flag_queries_only_ipv6(self):
        code, output, mock = run_script(
            ["192.168.1.1", "--v6"], ["2001:db8::1"])
        self.assertEqual(code, 0)
        mock.assert_called_once_with("192.168.1.1", ip_version=6)
        self.assertEqual(output, "2001:db8::1\n")

    def test_failure_returns_nonzero(self):
        with patch("porkbun_ddns.scripts.fritzbox_ips.get_ips_from_fritzbox",
                   side_effect=Exception("boom")):
            code = fritzbox_ips.main(["192.168.1.1"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()