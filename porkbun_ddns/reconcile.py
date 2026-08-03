"""Pure reconciliation of desired IPs against a frozen DNS record snapshot.

Decides, with no I/O and no state, what should be ensured (created or
replaced) so the DNS records for an fqdn match the desired IPs. The
``ip.version -> record_type`` mapping lives here, not in the caller.
"""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address
from typing import NamedTuple

__all__ = ["Ensure", "reconcile"]


class Ensure(NamedTuple):
    """An intent to ensure one DNS record for ``fqdn``.

    ``replacing_id`` is ``None`` when the record should be created fresh and
    set to the id of an existing record that should be deleted and recreated.
    """

    record_type: str  # "A" | "AAAA"
    fqdn: str
    content: str  # ip.exploded
    replacing_id: str | None  # None = create-new, set = replace-existing-by-id


def reconcile(
    existing_records: list[dict],
    desired_ips: list[IPv4Address | IPv6Address],
    fqdn: str,
) -> list[Ensure]:
    """Decide what to ensure given a FROZEN snapshot and desired IPs.

    Pure: no I/O, no client, no mutation of ``existing_records``. The same
    snapshot is used for every desired ip (frozen semantics), so each ip is
    reconciled against the same starting point.
    """
    actions: list[Ensure] = []
    for ip in desired_ips:
        record_type = "A" if ip.version == 4 else "AAAA"
        content = ip.exploded
        replaced: set[tuple[str, str]] = set()  # (record_type, content) ensured
        for record in existing_records:
            if record.get("name") != fqdn:
                continue
            rtype = record.get("type")
            if rtype in ("ALIAS", "CNAME") or (
                rtype == record_type and record.get("content") != content
            ):
                # Replace existing: overwrite ALIAS/CNAME or update a stale
                # record of the same type. A matching same-type record with
                # equal content is up-to-date and deliberately NOT replaced.
                actions.append(
                    Ensure(record_type, fqdn, content, record.get("id")))
                replaced.add((record_type, content))
        # Create missing / create new: no record of this type exists for the
        # fqdn (ALIAS/CNAME does not count), and no replace already ensured it.
        has_type = any(
            r.get("name") == fqdn and r.get("type") == record_type
            for r in existing_records
        )
        if not has_type and (record_type, content) not in replaced:
            actions.append(Ensure(record_type, fqdn, content, None))
    return actions
