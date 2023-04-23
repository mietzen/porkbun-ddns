import argparse
import sys
import traceback
from .porkbun_ddns import PorkbunDDNS, PorkbunDDNS_Error


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("config", help="Path to config file")
    parser.add_argument("domain", help="Domain to be updated")

    subdomain = parser.add_mutually_exclusive_group()
    subdomain.add_argument('subdomain', nargs='?',
                           default=None, help="Subdomain")

    public_ips = parser.add_mutually_exclusive_group()
    public_ips.add_argument('-i', '--public-ips', nargs='*',
                            default=None, help="Public IPs (v4 and or v6)")

    fritzbox = parser.add_mutually_exclusive_group()
    fritzbox.add_argument('-f', '--fritzbox', default=None,
                          help="IP or Domain of your Fritz!Box")

    ip = parser.add_mutually_exclusive_group()
    ip.add_argument('-4', '--ipv4-only', action='store_true',
                    help="Only set/update IPv4 A Records")
    ip.add_argument('-6', '--ipv6-only', action='store_true',
                    help="Only set/update IPv6 AAAA Records")

    if len(sys.argv) == 1:
        parser.print_help()

    args = parser.parse_args(argv)

    ipv4 = args.ipv4_only
    ipv6 = args.ipv6_only
    if not any([ipv4, ipv6]):
        ipv4 = ipv6 = True

    try:
        porkbun_ddns = PorkbunDDNS(config=args.config, domain=args.domain,
                                   public_ips=args.public_ips, fritzbox_ip=args.fritzbox,
                                   ipv4=ipv4, ipv6=ipv6)
        porkbun_ddns.set_subdomain(args.subdomain)
        porkbun_ddns.update_records()
    except PorkbunDDNS_Error as e:
        sys.stderr.write("Error: " + str(e))
        sys.exit(1)
    except Exception as e:
        sys.stderr.write("This shouldn't have happened!")
        sys.stderr.write("Error: " + str(e))
        sys.stderr.write(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
