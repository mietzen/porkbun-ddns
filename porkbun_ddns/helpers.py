import urllib.request
import xml.etree.ElementTree as ET
import socket
import logging

logger = logging.getLogger()

def check_ipv6_connectivity() -> bool:
    """Check IPv6 connectivity
    Source: Pandu Poluan, https://stackoverflow.com/a/66249915
    
    Returns:
        bool: IPv6 connectivity
    """
    if socket.has_ipv6:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.bind(('v6.ident.me', 0))
            return True
        except OSError:
            logger.warning('No IPv6 connectivity!')
        finally:
            if sock:
                sock.close()
    return False

def get_ips_from_fritzbox(fritzbox_ip):
    """Retrieves the IP address of the Fritzbox router's external network interface.

    Args:
        fritzbox_ip (str): The IP address of the Fritzbox router.

    Returns:
        str: The IP address of the Fritzbox router's external network interface.

    Raises:
        urllib.error.URLError: If there is a problem opening the URL.

        ValueError: If the provided `fritzbox_ip` is not a valid IP address.

        AttributeError: If the requested field is not found in the XML response.
    """

    schema = 'GetExternalIPAddress'
    field = 'NewExternalIPAddress'

    req = urllib.request.Request(
        'http://' + fritzbox_ip + ':49000/igdupnp/control/WANIPConn1')
    req.add_header('Content-Type', 'text/xml; charset="utf-8"')
    req.add_header(
        'SOAPAction', 'urn:schemas-upnp-org:service:WANIPConnection:1#' + schema)
    data = '<?xml version="1.0" encoding="utf-8"?>' + \
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">' + \
        '<s:Body>' + \
        '<u:' + schema + ' xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1" />' + \
        '</s:Body>' + \
        '</s:Envelope>'
    req.data = data.encode('utf8')
    return ET.fromstring(urllib.request.urlopen(req).read()).find('.//' + field).text
