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

```shell
$ porkbun-ddns "./config.json" my.domain my.subdomain

# Set IP's explicit
$ porkbun-ddns "./config.json" my.domain my.subdomain -i '1.2.3.4' '1234:abcd:0:4567::8900'

# Use Fritz!Box to obtain IP's
$ porkbun-ddns "./config.json" my.domain my.subdomain -f fritz.box
```

You can set up a cron job get the full path to porkbun-ddns with `which porkbun-ddns`, then execute `crontab -e` and add the following line:

```
*/30 * * * * <PORKBUN-DDNS-PATH>/porkbun-ddns "<YOUR-PATH>/config.json" my.domain my.subdomain >/dev/null 2>&1
```

# Docker WIP

## Usage

### docker run

```shell
docker run -d mietzen/porkbun-ddns:latest
```

### docker-compose

```yaml
---

```


# Python

## Usage

```python
from porkbun_ddns import PorkbunDDNS

porkbun_ddns = PorkbunDDNS('./config.json', 'my.domain', 'my.subdomain')
porkbun_ddns_ip = PorkbunDDNS('./config.json', 'my.domain', 'my.subdomain', public_ips=['1.2.3.4','1234:abcd:0:4567::8900'])
porkbun_ddns_fritz = PorkbunDDNS('./config.json', 'my.domain', 'my.subdomain', fritzbox='fritz.box')
```
