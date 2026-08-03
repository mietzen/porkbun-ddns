from __future__ import annotations

import logging
import urllib.request
from collections.abc import Callable
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.error import URLError

from porkbun_ddns.errors import PorkbunDDNS_Error

logger = logging.getLogger("porkbun_ddns")


class PublicIPResolver:
    """Resolves the public IP addresses of the network.

    Two sources: an explicit static override, or public-HTTP discovery. The
    ``_urlopen`` argument is an internal seam for tests (leading underscore =
    private, not part of the documented interface).
    """

    def __init__(
            self,
            ipv4: bool = True,
            ipv6: bool = True,
            _urlopen: Callable = urllib.request.urlopen,
    ) -> None:
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self._urlopen = _urlopen

    def resolve(
            self,
            static_ips: list[str] | None = None,
    ) -> list[IPv4Address | IPv6Address]:
        """Return the resolved public IPs, deduplicated and non-unspecified.

        Raises:
        ------
            PorkbunDDNS_Error: If no IP could be obtained.
        """
        if static_ips:
            public_ips = [x.strip() for x in static_ips]
        else:
            public_ips = self._from_public_http()

        public_ips = list(dict.fromkeys(public_ips))

        if not public_ips:
            raise PorkbunDDNS_Error("Failed to obtain IP Addresses!")

        return [ip_address(x) for x in public_ips if not ip_address(x).is_unspecified]

    def _from_public_http(self) -> list[str]:
        ips = []
        if self.ipv4:
            ips.append(self._fetch_first_working(
                ["https://v4.ident.me",
                 "https://api.ipify.org",
                 "https://ipv4.icanhazip.com"]))
        if self.ipv6:
            ips.append(self._fetch_first_working(
                ["https://v6.ident.me",
                 "https://api6.ipify.org",
                 "https://ipv6.icanhazip.com"]))
        return [ip for ip in ips if ip]

    def _fetch_first_working(self, urls: list[str]) -> str | None:
        for url in urls:
            try:
                response = self._urlopen(url, timeout=30)
                if response.getcode() == 200:
                    return response.read().decode("utf-8").strip()
                logger.warning(
                    "Failed to retrieve IP Address from %s! HTTP status code: %s",
                    url, response.getcode())
            except URLError as err:
                logger.warning("Error reaching %s! - %s", url, err.reason)
        return None