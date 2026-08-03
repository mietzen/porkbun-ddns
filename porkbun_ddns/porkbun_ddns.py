from __future__ import annotations

import json
import logging
import urllib.request
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.error import URLError

from porkbun_ddns.api import PorkbunAPIClient
from porkbun_ddns.config import Credentials, RetryPolicy
from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.helpers import get_ips_from_fritzbox

logger = logging.getLogger("porkbun_ddns")


class PorkbunDDNS:
    """A class for updating dynamic DNS records for a Porkbun domain.
    """

    def __init__(
            self,
            credentials: Credentials,
            retry: RetryPolicy,
            domain: str,
            public_ips: list | None = None,
            fritzbox_ip: str | None = None,
            ipv4: bool = True,
            ipv6: bool = True,
            client: PorkbunAPIClient | None = None,
    ) -> None:

        self.credentials = credentials
        self.client = client or PorkbunAPIClient(credentials, retry)
        self.static_ips = public_ips
        self.domain = domain.lower()
        self.records = None
        self.fritzbox_ip = fritzbox_ip
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.fqdn = self.domain
        self.subdomain = "@"
        self.changes: list = []

    def set_subdomain(self, subdomain: str) -> None:
        self.subdomain = subdomain.lower()
        if self.subdomain == "@":
            self.fqdn = self.domain
        else:
            self.fqdn = f"{self.subdomain}.{self.domain}"

    def get_public_ips(self) -> list:
        """Retrieve the public IP addresses of the network.
        """
        public_ips: set | list | None
        if self.static_ips:
            public_ips = self.static_ips
        else:
            public_ips = []
            if self.fritzbox_ip:
                if self.ipv4:
                    public_ips.append(
                        get_ips_from_fritzbox(self.fritzbox_ip, ip_version=4))
                if self.ipv6:
                    public_ips.append(
                        get_ips_from_fritzbox(self.fritzbox_ip, ip_version=6))
            else:
                if self.ipv4:
                    urls = ["https://v4.ident.me",
                            "https://api.ipify.org",
                            "https://ipv4.icanhazip.com"]
                    for url in urls:
                        try:
                            with urllib.request.urlopen(url, timeout=30) as response:
                                if response.getcode() == 200:
                                    public_ips.append(
                                        response.read().decode("utf-8").strip())
                                    break
                                logger.warning(
                                    "Failed to retrieve IPv4 Address from %s! HTTP status code: %s", url, str(response.code()))
                        except URLError as err:
                            logger.warning(
                                "Error reaching %s! - %s", url, err.reason)
                if self.ipv6:
                    urls = ["https://v6.ident.me",
                            "https://api6.ipify.org",
                            "https://ipv6.icanhazip.com"]
                    for url in urls:
                        try:
                            with urllib.request.urlopen(url, timeout=30) as response:
                                if response.getcode() == 200:
                                    public_ips.append(
                                        response.read().decode("utf-8").strip())
                                    break
                                logger.warning(
                                    "Failed to retrieve IPv6 Address from %s! HTTP status code: %s", url, str(response.code()))
                        except URLError as err:
                            logger.warning(
                                "Error reaching %s! - %s", url, err.reason)

            public_ips = set(public_ips)

        if not public_ips:
            raise PorkbunDDNS_Error("Failed to obtain IP Addresses!")

        return [ip_address(x) for x in public_ips if not ip_address(x).is_unspecified]

    def get_records(self) -> list:
        """Retrieve the DNS records for the specified domain.
        """
        return self.client.retrieve_records(self.domain)

    def update_records(self):
        """Update DNS records for the specified domain.
        """
        self.records = self.get_records()
        domain_names = [x["name"] for x in self.records if x["type"]
                        in ["A", "AAAA", "ALIAS", "CNAME"]]
        for ip in self.get_public_ips():
            record_type = "A" if ip.version == 4 else "AAAA"
            if self.fqdn in domain_names:
                for i in self.records:
                    if i["name"] == self.fqdn:
                        # Overwrite ALIAS and CNAME
                        if i["type"] in ["ALIAS", "CNAME"]:
                            logger.debug("Overwrite ALIAS and CNAME, with:\n{}".format(json.dumps(
                                {"name": self.fqdn, "type": record_type, "content": str(ip.exploded)})))
                            self._delete_record(i["id"])
                            self._create_records(ip, record_type)
                            self._record_change(record_type, i["content"], ip.exploded)
                        # Update existing entry
                        if i["type"] == record_type and i["content"] != ip.exploded:
                            logger.debug("Update existing entry, with:\n{}".format(json.dumps(
                                {"name": self.fqdn, "type": record_type, "content": str(ip.exploded)})))
                            self._delete_record(i["id"])
                            self._create_records(ip, record_type)
                            self._record_change(record_type, i["content"], ip.exploded)
                        # Create missing A or AAAA entry
                        if i["type"] in ["A", "AAAA"] and record_type not in [x["type"] for x in self.records if
                                                                              x["name"] == self.fqdn]:
                            logger.debug("Create missing A or AAAA entry, with:\n{}".format(json.dumps(
                                {"name": self.fqdn, "type": record_type, "content": str(ip.exploded)})))
                            self._create_records(ip, record_type)
                            self._record_change(record_type, None, ip.exploded)
                            # Update records
                            self.records = self.get_records()
                        # Everything is up to date
                        if i["type"] == record_type and i["content"] == ip.exploded:
                            logger.info("{}-Record of {} is up to date!".format(
                                i["type"], i["name"]))
            else:
                logger.debug("Create new record, with:\n{}".format(json.dumps(
                    {"name": self.fqdn, "type": record_type, "content": str(ip.exploded)})))
                # Create new record
                self._create_records(ip, record_type)
                self._record_change(record_type, None, ip.exploded)
                # Update records
                self.records = self.get_records()

    def _record_change(self, record_type: str, old_ip: str | None, new_ip: str) -> None:
        """Record a DNS change for the aggregated webhook changelog.
        """
        self.changes.append({
            "record_type": record_type,
            "fqdn": self.fqdn,
            "old_ip": old_ip,
            "new_ip": new_ip,
        })

    def delete_records(self):
            """Delete A and AAAA DNS record for set record.
            """
            self.records = self.get_records()
            domain_names = [x["name"] for x in self.records if x["type"]
                            in ["A", "AAAA"]]
            if self.fqdn in domain_names:
                for i in self.records:
                    if i["name"] == self.fqdn and i["type"] in ["A", "AAAA"]:
                        logger.debug("Deleting existing entry:\n{}".format(json.dumps(
                            {"name": self.fqdn, "type": i["type"], "content": str(i["content"])})))
                        self._delete_record(i["id"])
            else:
                logger.debug("Record not found:\n{}".format(json.dumps(
                    {"name": self.fqdn, "type": i["type"], "content": str(i["content"])})))

    def _delete_record(self, domain_id: str):
        """Delete a DNS record with the given domain ID.
        """
        if self.records:
            type, name, content = next(
                (x["type"], x["name"], x["content"])
                for x in self.records
                if x["id"] == domain_id
            )
            status = self.client.delete_record(self.domain, domain_id)
            logger.info(f"Deleting {type}-Record for {name} with content: {content}, Status: {status}")

    def _create_records(self, ip: IPv4Address | IPv6Address, record_type: str):
        """Create DNS records for the subdomain with the given IP address and type.
        """
        status = self.client.create_record(
            self.domain, self.subdomain, record_type, ip.exploded)
        logger.info(f"Creating {record_type}-Record for {self.fqdn} with content: {ip.exploded}, Status: {status}")
