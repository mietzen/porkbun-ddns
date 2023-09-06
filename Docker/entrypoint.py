import os
import sys
import logging
from time import sleep
from porkbun_ddns import PorkbunDDNS

logger = logging.getLogger('porkbun_ddns')
logger.setLevel(logging.INFO)
logger.propagate = False

sleep_time = int(os.getenv('SLEEP', 300))
domain = os.getenv('DOMAIN', None)

public_ips = None
if os.getenv('PUBLIC_IPS', None):
    public_ips = [x.strip() for x in os.getenv('PUBLIC_IPS', None).split(',')]
fritzbox = os.getenv('FRITZBOX', None)

config = {
    'secretapikey': os.getenv('SECRETAPIKEY'),
    'apikey': os.getenv('APIKEY')
}

ipv4 = ipv6 = True
if os.getenv('IPV4_ONLY', 'False').lower() in ('true', '1', 't'):
    ipv6 = False
if os.getenv('IPV6_ONLY', 'False').lower() in ('true', '1', 't'):
    ipv4 = False

if os.getenv('DEBUG', 'False').lower() in ('true', '1', 't'):
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)

if not all([os.getenv('DOMAIN'), os.getenv('SECRETAPIKEY'), os.getenv('APIKEY')]):
    logger.info('Please set DOMAIN, SECRETAPIKEY and APIKEY')
    sys.exit(1)

if not any([ipv4, ipv6]):
    logger.info('You can not set both IPV4_ONLY and IPV6_ONLY to TRUE')
    sys.exit(1)

porkbun_ddns = PorkbunDDNS(config, domain, public_ips=public_ips,
                           fritzbox_ip=fritzbox, ipv4=ipv4, ipv6=ipv6)

while True:
    subdomains = os.getenv('SUBDOMAINS', '')
    if subdomains:
        for subdomain in subdomains.replace(' ', '').split(','):
            porkbun_ddns.set_subdomain(subdomain)
            porkbun_ddns.update_records()
    else:
        porkbun_ddns.update_records()
    logger.info('Sleeping... {}s'.format(sleep_time))
    sleep(sleep_time)
