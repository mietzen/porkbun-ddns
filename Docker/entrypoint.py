import logging
import sys
import os
import time
from porkbun_ddns.config import Config, get_secret_from_env, DEFAULT_ENDPOINT
from porkbun_ddns.porkbun_ddns import PorkbunDDNS

logger = logging.getLogger("porkbun_ddns")
logging.basicConfig(level=logging.INFO)

def main():
    domain = os.getenv("DOMAIN")
    apikey = get_secret_from_env("APIKEY")
    secretapikey = get_secret_from_env("SECRETAPIKEY")
    
    if not all([domain, apikey, secretapikey]):
        logger.info("Please set DOMAIN, SECRETAPIKEY and APIKEY")
        sys.exit(1)
    
    ipv4 = ipv6 = False
    if os.getenv('IPV4', 'True').lower() in ('true', '1', 't'):
        ipv4 = True
    if os.getenv('IPV6', 'False').lower() in ('true', '1', 't'):
        ipv6 = True
    
    if not any([ipv4, ipv6]):
        logger.info("No Protocol selected! Please set IPV4 and/or IPV6 TRUE")
        sys.exit(1)
    
    config = Config(endpoint=DEFAULT_ENDPOINT, apikey=apikey, secretapikey=secretapikey)
    porkbun_ddns = PorkbunDDNS(config, domain, ipv4=ipv4, ipv6=ipv6)
    
    logger.info("Starting Porkbun DDNS update process...")
    try:
        while True:
            subdomains = os.getenv('SUBDOMAINS', '')
            if subdomains:
                for subdomain in subdomains.replace(' ', '').split(','):
                    porkbun_ddns.set_subdomain(subdomain)
                    porkbun_ddns.update_records()
            else:
                porkbun_ddns.update_records()
            
            sleep_time = int(os.getenv("SLEEP", "300"))
            logger.info("Sleeping... {}s".format(sleep_time))
            time.sleep(sleep_time)
    except Exception as e:
        logger.error(f"Failed to update DNS records: {e}")
        sys.exit(1)
    
if __name__ == "__main__":
    main()
