"""Hand-written test doubles for the Porkbun API client seam."""

from __future__ import annotations

from porkbun_ddns.errors import PorkbunDDNS_Error


class StubPorkbunAPIClient:
    """Configurable stub of :class:`PorkbunAPIClient` for orchestrator tests.

    ``retrieve_records`` returns the canned records list and records each
    ``create_record``/``delete_record`` call for assertion; both return the
    canned ``status`` string.
    """

    def __init__(self, records: list | None = None, status: str = "SUCCESS") -> None:
        self.records = records if records is not None else []
        self.status = status
        self.created: list[tuple] = []
        self.deleted: list[tuple] = []

    def retrieve_records(self, domain: str) -> list:
        if self.status != "SUCCESS":
            raise PorkbunDDNS_Error(
                f"Failed to get records.\nMake sure you specified the correct "
                f"domain ({domain}),\nand that API access has been enabled for "
                "this domain.",
            )
        return self.records

    def create_record(self, domain: str, name: str, record_type: str,
                      content: str, ttl: int = 600) -> str:
        self.created.append((domain, name, record_type, content, ttl))
        return self.status

    def delete_record(self, domain: str, record_id: str) -> str:
        self.deleted.append((domain, record_id))
        return self.status
