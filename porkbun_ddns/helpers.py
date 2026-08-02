import logging
import urllib.request
import xml.etree.ElementTree as ET


def parse_log_level(level: str | None, *, default: int = logging.INFO) -> int:
    """Parses a logging level name to its ``logging`` level integer.

    Accepts the standard level names (case-insensitive): ``DEBUG``, ``INFO``,
    ``WARNING`` (or ``WARN``), ``ERROR`` and ``CRITICAL``. Unknown or empty
    values log a warning on the ``porkbun_ddns`` logger and fall back to
    ``default`` (INFO).

    Args:
    ----
        level (str | None): The level name to parse, or None.
        default (int): The level to fall back to on unknown values.

    Returns:
    -------
        int: The matching ``logging`` level.
    """

    if not level:
        return default

    normalized = level.strip().upper()
    if not normalized:
        return default

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    if normalized in level_map:
        return level_map[normalized]

    logging.getLogger("porkbun_ddns").warning(
        "Unknown log level '%s', falling back to %s",
        level,
        logging.getLevelName(default),
    )
    return default


def get_ips_from_fritzbox(fritzbox_ip, ip_version=4):
    """Retrieves the IP addresses of the Fritzbox router's external network interface.

    Args:
    ----
        fritzbox_ip (str): The IP address of the Fritzbox router.

    Returns:
    -------
        str: The IP address of the Fritzbox router's external network interface.

    Raises:
    ------
        urllib.error.URLError: If there is a problem opening the URL.

        ValueError: If the provided `fritzbox_ip` is not a valid IP address.

        AttributeError: If the requested field is not found in the XML response.
    """

    schema = "GetExternalIPAddress"
    field = "NewExternalIPAddress"

    if ip_version == 6:
        schema = "X_AVM_DE_GetExternalIPv6Address"
        field = "NewExternalIPv6Address"

    req = urllib.request.Request(
        "http://" + fritzbox_ip + ":49000/igdupnp/control/WANIPConn1")
    req.add_header("Content-Type", 'text/xml; charset="utf-8"')
    req.add_header(
        "SOAPAction", "urn:schemas-upnp-org:service:WANIPConnection:1#" + schema)
    data = '<?xml version="1.0" encoding="utf-8"?>' + \
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">' + \
        "<s:Body>" + \
        '<u:GetExternalIPAddress xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1" />' + \
        "</s:Body>" + \
        "</s:Envelope>"
    req.data = data.encode("utf8")
    return ET.fromstring(urllib.request.urlopen(req).read()).find(".//" + field).text
