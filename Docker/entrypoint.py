import os
import sys
import logging
from time import sleep
from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import (
    AppConfig,
    Credentials,
    DEFAULT_ENDPOINT,
    RetryPolicy,
    WebhookConfig,
)
from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.helpers import parse_log_level
from porkbun_ddns.webhook import fire_webhook

logger = logging.getLogger('porkbun_ddns')
log_level = os.getenv('LOG_LEVEL', None)
if log_level:
    logger.setLevel(parse_log_level(log_level))
elif os.getenv('DEBUG', 'False').lower() in ('true', '1', 't'):
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

app = AppConfig(
    credentials=Credentials(
        apikey=os.getenv('APIKEY'),
        secretapikey=os.getenv('SECRETAPIKEY'),
        endpoint=os.getenv('API_ENDPOINT', DEFAULT_ENDPOINT),
    ),
    retry=RetryPolicy(
        retry_count=int(os.getenv('RETRY_COUNT', '3')),
        retry_delay=int(os.getenv('RETRY_DELAY', '5')),
    ),
    webhook=WebhookConfig(
        webhook_url=os.getenv('WEBHOOK_URL') or '',
        webhook_template=os.getenv('WEBHOOK_TEMPLATE') or '',
        webhook_template_file=os.getenv('WEBHOOK_TEMPLATE_FILE') or '',
    ),
)

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

porkbun_ddns = PorkbunDDNS(app.credentials, app.retry, domain, public_ips=public_ips,
                           fritzbox_ip=fritzbox, ipv4=ipv4, ipv6=ipv6)

while True:
    subdomains = os.getenv('SUBDOMAINS', '')
    if subdomains:
        for subdomain in subdomains.replace(' ', '').split(','):
            porkbun_ddns.set_subdomain(subdomain)
            porkbun_ddns.update_records()
    else:
        porkbun_ddns.update_records()
    if porkbun_ddns.changes:
        fire_webhook(app.webhook, porkbun_ddns.changes, porkbun_ddns.domain)
        porkbun_ddns.changes = []
    logger.info('Sleeping... {}s'.format(sleep_time))
    sleep(sleep_time)
