import argparse
import logging
import sys
import traceback

from porkbun_ddns import PorkbunDDNS
from porkbun_ddns.config import extract_config, get_config_file_default, create_default_config_file
from porkbun_ddns.errors import PorkbunDDNS_Error

logger = logging.getLogger("porkbun_ddns")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("domain", help="Domain to be updated")

    parser.add_argument("-c", "--config", help=f"Path to config file "
                                               f"(default: {get_config_file_default()})")
    parser.add_argument("-e", "--endpoint", help="The endpoint")
    parser.add_argument("-pk", "--apikey", help="The Porkbun-API-key")
    parser.add_argument("-sk", "--secretapikey", help="The secret API-key")

    subdomains = parser.add_mutually_exclusive_group()
    subdomains.add_argument("subdomains", nargs="*",
                           default=None, help="Subdomain(s)")

    public_ips = parser.add_mutually_exclusive_group()
    public_ips.add_argument("-i", "--public-ips", nargs="*",
                            default=None, help="Public IPs (v4 and or v6)")

    fritzbox = parser.add_mutually_exclusive_group()
    fritzbox.add_argument("-f", "--fritzbox", default=None,
                          help="IP or Domain of your Fritz!Box")

    ip = parser.add_mutually_exclusive_group()
    ip.add_argument("-4", "--ipv4-only", action="store_true",
                    help="Only set/update IPv4 A Records")
    ip.add_argument("-6", "--ipv6-only", action="store_true",
                    help="Only set/update IPv6 AAAA Records")

    verbose = parser.add_mutually_exclusive_group()
    verbose.add_argument("-v", "--verbose", action="store_true",
                    help="Show Debug Output")

    env_only = parser.add_mutually_exclusive_group()
    env_only.add_argument("--env_only", action="store_true",
                    help="Don't use any config, "
                    "get all variables from the environment")

    if not argv:
        parser.print_help()
        exit(1)
    try:
        args = parser.parse_args(argv)

        if args.env_only:
            args.config = None
        elif args.config is None:
            args.config = get_config_file_default()
            create_default_config_file()

        if args.verbose:
            logger.setLevel(logging.DEBUG)
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        config = extract_config(args)
        ipv4 = args.ipv4_only
        ipv6 = args.ipv6_only
        if not any([ipv4, ipv6]):
            ipv4 = ipv6 = True

        porkbun_ddns = PorkbunDDNS(config=config, domain=args.domain,
                                   public_ips=args.public_ips, fritzbox_ip=args.fritzbox,
                                   ipv4=ipv4, ipv6=ipv6)
        if args.subdomains:
            for s in args.subdomains:
                porkbun_ddns.set_subdomain(s)
                porkbun_ddns.update_records()
        else:
            porkbun_ddns.update_records()
    except PorkbunDDNS_Error as e:
        logger.error("Error: " + str(e))
        exit(1)
    except Exception as e:
        logger.error("This shouldn't have happened!")
        logger.error("Error: " + str(e))
        logger.error(traceback.format_exc())
        exit(1)


if __name__ == "__main__":
    main()
