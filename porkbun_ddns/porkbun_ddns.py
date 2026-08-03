from __future__ import annotations

import json
import logging

from porkbun_ddns.api import PorkbunAPIClient
from porkbun_ddns.config import Credentials, RetryPolicy
from porkbun_ddns.reconcile import Ensure, reconcile
from porkbun_ddns.resolver import PublicIPResolver

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
            ipv4: bool = True,
            ipv6: bool = True,
            client: PorkbunAPIClient | None = None,
            resolver: PublicIPResolver | None = None,
    ) -> None:

        self.credentials = credentials
        self.client = client or PorkbunAPIClient(credentials, retry)
        self.static_ips = public_ips
        self.domain = domain.lower()
        self.records = None
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.resolver = resolver or PublicIPResolver(ipv4=ipv4, ipv6=ipv6)
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
        return self.resolver.resolve(self.static_ips)

    def get_records(self) -> list:
        """Retrieve the DNS records for the specified domain.
        """
        return self.client.retrieve_records(self.domain)

    def update_records(self):
        """Update DNS records for the specified domain.

        Fetches the current records once, derives the reconciliation plan
        purely with :func:`reconcile`, then executes the ``Ensure`` intents.
        """
        records = self.client.retrieve_records(self.domain)
        ips = self.get_public_ips()
        actions: list[Ensure] = reconcile(records, ips, self.fqdn)
        for action in actions:
            if action.replacing_id is not None:
                old = next(
                    r for r in records if r["id"] == action.replacing_id)
                logger.debug("Update existing entry, with:\n%s", json.dumps(
                    {"name": self.fqdn, "type": action.record_type,
                     "content": action.content}))
                status = self.client.delete_record(
                    self.domain, action.replacing_id)
                logger.info(
                    f"Deleting {old['type']}-Record for {old['name']} with "
                    f"content: {old['content']}, Status: {status}")
                status = self.client.create_record(
                    self.domain, self.subdomain,
                    action.record_type, action.content)
                logger.info(
                    f"Creating {action.record_type}-Record for {self.fqdn} "
                    f"with content: {action.content}, Status: {status}")
                self._record_change(
                    action.record_type, old["content"], action.content)
            else:
                logger.debug("Create new record, with:\n%s", json.dumps(
                    {"name": self.fqdn, "type": action.record_type,
                     "content": action.content}))
                status = self.client.create_record(
                    self.domain, self.subdomain,
                    action.record_type, action.content)
                logger.info(
                    f"Creating {action.record_type}-Record for {self.fqdn} "
                    f"with content: {action.content}, Status: {status}")
                self._record_change(action.record_type, None, action.content)
        # Up-to-date log derived from the gap: desired (record_type, content)
        # pairs that produced no Ensure are already correct.
        ensured = {(action.record_type, action.content) for action in actions}
        for ip in ips:
            record_type = "A" if ip.version == 4 else "AAAA"
            content = ip.exploded
            if (record_type, content) not in ensured:
                logger.info(f"{record_type}-Record of {self.fqdn} is up to date!")

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
                        status = self.client.delete_record(self.domain, i["id"])
                        logger.info(
                            f"Deleting {i['type']}-Record for {i['name']} with "
                            f"content: {i['content']}, Status: {status}")
            else:
                logger.debug("Record not found:\n{}".format(json.dumps(
                    {"name": self.fqdn, "type": i["type"], "content": str(i["content"])})))
