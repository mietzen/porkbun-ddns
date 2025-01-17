import os
import sys
import logging
from time import sleep
from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import Config, DEFAULT_ENDPOINT

logger = logging.getLogger('porkbun_ddns')
if os.getenv('DEBUG', 'False').lower() in ('true', '1', 't'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
logger.propagate = False
logFormatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

sleep_time = int(os.getenv('SLEEP', 300))
domain = os.getenv('DOMAIN', None)

if os.getenv('IPV4_ONLY', None) or os.getenv('IPV6_ONLY', None):
    raise PorkbunDDNS_Error('IPV4_ONLY and IPV6_ONLY are DEPRECATED and have been removed since v1.1.0')

public_ips = None
if os.getenv('PUBLIC_IPS', None):
    public_ips = [x.strip() for x in os.getenv('PUBLIC_IPS', None).split(',')]
fritzbox = os.getenv('FRITZBOX', None)

config = Config(DEFAULT_ENDPOINT, os.getenv('APIKEY'), os.getenv('SECRETAPIKEY'))

ipv4 = ipv6 = False
if os.getenv('IPV4', 'True').lower() in ('true', '1', 't'):
    ipv4 = True
if os.getenv('IPV6', 'False').lower() in ('true', '1', 't'):
    ipv6 = True
    
if not all([os.getenv('DOMAIN'), os.getenv('SECRETAPIKEY'), os.getenv('APIKEY')]):
    logger.info('Please set DOMAIN, SECRETAPIKEY and APIKEY')
    sys.exit(1)

if not any([ipv4, ipv6]):
    logger.info('No Protocol selected! Please set IPV4 and/or IPV6 TRUE')
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
