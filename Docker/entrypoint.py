import os
import sys
from time import sleep
from porkbun_ddns import PorkbunDDNS, cli

if os.getenv('INTEGRATION_TEST'):
    print('\n------------------------------------')
    print('INTEGRATION TEST! Printing help menu')
    print('------------------------------------\n')
    while True:
        try:
            cli.main(argv=['-h'])
        except SystemExit:
            pass
        finally:
            print('\n------------------------------------')
            print('Sleeping...')
            print('------------------------------------\n')
            sleep(300)

if not all([os.getenv('DOMAIN'), os.getenv('SECRETAPIKEY'), os.getenv('APIKEY')]):
    print('Please set DOMAIN, SECRETAPIKEY and APIKEY')
    sys.exit(1)

domain = os.getenv('DOMAIN', None)
public_ips = None
if os.getenv('PUBLIC_IPS', None):
    public_ips = [x.strip() for x in os.getenv('PUBLIC_IPS', None).split(',')]
fritzbox = os.getenv('FRITZBOX', None)
sleep_time = os.getenv('SLEEP', 300)

config = {
    'secretapikey': os.getenv('SECRETAPIKEY'),
    'apikey': os.getenv('APIKEY')
}

ipv4 = ipv6 = True
if os.getenv('IPV4_ONLY', 'False').lower() in ('true', '1', 't'):
    ipv6 = False
if os.getenv('IPV6_ONLY', 'False').lower() in ('true', '1', 't'):
    ipv4 = False

if not any([ipv4, ipv6]):
    print('You can not set both IPV4_ONLY and IPV6_ONLY to TRUE')
    sys.exit(1)

porkbun_ddns = PorkbunDDNS(config, domain, public_ips=public_ips,
                           fritzbox_ip=fritzbox, ipv4=ipv4, ipv6=ipv6)

while True:
    subdomains = os.getenv('SUBDOMAINS').split(',')
    if subdomains:
        for subdomain in os.getenv('SUBDOMAINS').split(','):
            porkbun_ddns.set_subdomain(subdomain)
            porkbun_ddns.update_records()
    else:
        porkbun_ddns.update_records()
    print('Sleeping... {}s'.format(sleep_time))
    sleep(sleep_time)
