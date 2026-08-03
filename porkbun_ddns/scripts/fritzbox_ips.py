"""Console-script entry point for discovering a Fritz!Box's external IPs.

Prints each discovered IP on its own line to stdout. Exits 0 on success,
non-zero on failure.
"""

from __future__ import annotations

import argparse
import sys

from porkbun_ddns.helpers import get_ips_from_fritzbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover the external IP address(es) of a Fritz!Box router.")
    parser.add_argument("fritzbox_ip", help="IP or domain of your Fritz!Box")
    family = parser.add_mutually_exclusive_group()
    family.add_argument("--v4", action="store_true",
                        help="Only query the IPv4 address")
    family.add_argument("--v6", action="store_true",
                        help="Only query the IPv6 address")
    args = parser.parse_args(argv)

    v4 = not args.v6  # default both; --v6 disables v4
    v6 = not args.v4  # default both; --v4 disables v6

    ips: list[str] = []
    try:
        if v4:
            ips.append(get_ips_from_fritzbox(args.fritzbox_ip, ip_version=4))
        if v6:
            ips.append(get_ips_from_fritzbox(args.fritzbox_ip, ip_version=6))
    except Exception as exc:  # noqa: BLE001 - script entry point, catch-all is intentional
        print(f"Failed to obtain IP from Fritz!Box: {exc}", file=sys.stderr)
        return 1

    for ip in ips:
        print(ip)
    return 0


if __name__ == "__main__":
    sys.exit(main())