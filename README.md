# Disclaimer

**This package is not related to or developed by Porkbun. No relationship between the developer of this package and Porkbun exists.**

**All trademarks, logos and brand names are the property of their respective owners. All company, product and service names used in this package are for identification purposes only. Use of these names,trademarks and brands does not imply endorsement.**

# Porkbun DDNS
`porkbun-ddns` is a unofficial DDNS-Client for Porkbun Domains.
This library will only update the records if the IP(s) have changed or the dns entry didn't exist before, it will also set/update A (IPv4) and AAAA (IPv6) records.


Since [porkbun-dynamic-dns-python](https://github.com/porkbundomains/porkbun-dynamic-dns-python) is deprecate and [ddclient](https://github.com/ddclient/ddclient/issues/528) has no more active maintainers, I took it into my own hands to code a decent DDNS Client for Porkbun.
Inspired by [con-f-use](https://github.com/con-f-use) [pull request](https://github.com/porkbundomains/porkbun-dynamic-dns-python/pull/6), I built a pip Package and a docker container.

I also containerized [cert-bun](https://github.com/mietzen/docker-cert-bun).

# CLI

## Install via pip

```shell
pip install porkbun-ddns
```

## Usage

```Shell
$ porkbun-ddns -h
usage: porkbun-ddns [-h] [-i [PUBLIC_IPS ...]] [-f FRITZBOX] [-4 | -6] config domain [subdomain]

positional arguments:
  config                Path to config file
  domain                Domain to be updated
  subdomain             Subdomain

options:
  -h, --help            show this help message and exit
  -i [PUBLIC_IPS ...], --public-ips [PUBLIC_IPS ...]
                        Public IPs (v4 and or v6)
  -f FRITZBOX, --fritzbox FRITZBOX
                        IP or Domain of your Fritz!Box
  -4, --ipv4-only       Only set/update IPv4 A Records
  -6, --ipv6-only       Only set/update IPv6 AAAA Records
```

Examples:

```shell
$ porkbun-ddns "./config.json" domain.com my_subdomain

# Set IP's explicit
$ porkbun-ddns "./config.json" domain.com my_subdomain -i '1.2.3.4' '1234:abcd:0:4567::8900'

# Use Fritz!Box to obtain IP's and set IPv4 A Record only
$ porkbun-ddns "./config.json" domain.com my_subdomain -f fritz.box -4
```

You can set up a cron job get the full path to porkbun-ddns with `which porkbun-ddns`, then execute `crontab -e` and add the following line:

```
*/30 * * * * <PORKBUN-DDNS-PATH>/porkbun-ddns "<YOUR-PATH>/config.json" domain.com my.subdomain >/dev/null 2>&1
```

# Docker-Compose

```yaml
version: "3"
services:
  porkbun-ddns:
    image: "mietzen/porkbun-ddns:latest"
    container_name: porkbun-ddns
    environment:
      DOMAIN: "domain.com" # Your Porkbun domain
      SUBDOMAINS: "my_subdomain,my_other_subdomain,my_subsubdomain.my_subdomain" # Subdomains comma spreaded
      SECRETAPIKEY: "<YOUR-SECRETAPIKEY>" # Your Porkbun Secret-API-Key
      APIKEY: "<YOUR-APIKEY>" # Your Porkbun API-Key
      # PUBLIC_IPS: "1.2.3.4,2001:043e::1" # Set if you got static IP's
      # FRITZBOX: "192.168.178.1" # Use Fritz!BOX to obtain Public IP's
      # SLEEP: "300" # Seconds to sleep between DynDNS runs
      # IPV4_ONLY: "FALSE" # Only set IPv4 address
      # IPV6_ONLY: "FALSE" # Only set IPv6 address
    restart: unless-stopped
```

# Python

```python
from porkbun_ddns import PorkbunDDNS

config = {
    'secretapikey': 'YOUR-SECRETAPIKEY',
    'apikey': 'YOUR-APIKEY'
}

porkbun_ddns = PorkbunDDNS(config, 'domain.com')
# porkbun_ddns = PorkbunDDNS('./config.json', 'domain.com')
# porkbun_ddns_ip = PorkbunDDNS('./config.json', 'domain.com', public_ips=['1.2.3.4','1234:abcd:0:4567::8900'])
# porkbun_ddns_fritz = PorkbunDDNS('./config.json', 'domain.com', fritzbox='fritz.box', ipv6=False)

porkbun_ddns.set_subdomain('my_subdomain')
porkbun_ddns.update_records()
```
