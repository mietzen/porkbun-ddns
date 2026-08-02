"""Jinja-templated webhook delivery, fired once per update pass on IP change."""

from __future__ import annotations

import logging
import urllib.request
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # datetime.UTC is Python 3.11+; keep 3.10 support
    from datetime import UTC
except ImportError:  # pragma: no cover - 3.10 fallback
    from datetime import timedelta, timezone
    UTC = timezone(timedelta(0))

import jinja2

from porkbun_ddns.config import Config

logger = logging.getLogger("porkbun_ddns")

DEFAULT_WEBHOOK_TEMPLATE: str = (
    '{"text": "IP changed: {{ old_ips | join(\', \') }} -> '
    '{{ new_ips | join(\', \') }} ({{ domain }})"}'
)


def _webhook_context(changes: Sequence[dict[str, Any]],
                     domain: str) -> dict[str, Any]:
    """Build the template context for the given changes.
    """
    old_ips = list(dict.fromkeys(
        change["old_ip"] for change in changes if change["old_ip"] is not None))
    new_ips = list(dict.fromkeys(
        change["new_ip"] for change in changes if change["new_ip"] is not None))
    return {
        "changes": list(changes),
        "old_ips": old_ips,
        "new_ips": new_ips,
        "domain": domain,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def render_webhook_payload(changes: Sequence[dict[str, Any]],
                           domain: str,
                           template: str | None = None,
                           template_file: str | None = None) -> str:
    """Render the webhook payload for the given changes.

    Template precedence: file > inline > built-in default. A missing or
    unreadable template file, or a template that fails to render, falls back to
    the next precedence level instead of crashing.
    """
    template_source = DEFAULT_WEBHOOK_TEMPLATE
    if template:
        template_source = template
    if template_file:
        try:
            template_source = Path(template_file).read_text()
        except OSError as err:
            fallback = "inline template" if template else "default template"
            logger.warning(
                "Failed to read webhook template file '%s': %s. "
                "Falling back to the %s.", template_file, err, fallback)
    context = _webhook_context(changes, domain)
    try:
        return jinja2.Environment().from_string(template_source).render(**context)
    except jinja2.TemplateError as err:
        logger.warning(
            "Failed to render webhook template: %s. "
            "Falling back to the default template.", err)
        return jinja2.Environment().from_string(
            DEFAULT_WEBHOOK_TEMPLATE).render(**context)


def send_webhook(url: str, payload: str) -> None:
    """POST the rendered payload to the webhook URL.

    Fire-and-forget: non-2xx responses, timeouts and connection errors are
    logged as warnings and never raise.
    """
    try:
        request = urllib.request.Request(
            url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if not 200 <= response.getcode() < 300:
                logger.warning(
                    "Webhook returned non-2xx status code: %s",
                    response.getcode())
    except Exception as err:  # noqa: BLE001 - fire-and-forget, never crash the loop
        logger.warning("Failed to send webhook to %s: %s", url, err)


def fire_webhook(config: Config,
                 changes: Sequence[dict[str, Any]],
                 domain: str) -> bool:
    """Render and send one aggregated webhook for the given changes.

    Sends nothing when no webhook URL is configured or no changes were
    recorded. Returns ``True`` when a webhook was sent.
    """
    if not config.webhook_url or not changes:
        return False
    payload = render_webhook_payload(
        changes,
        domain,
        template=config.webhook_template,
        template_file=config.webhook_template_file,
    )
    send_webhook(config.webhook_url, payload)
    return True
