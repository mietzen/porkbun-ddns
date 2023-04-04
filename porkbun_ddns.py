#!/usr/bin/env python

import argparse
import json
import sys
import ipaddress
import urllib.request
import xml.etree.ElementTree as ET

def err(msg, *args, **kwargs):
    msg = "Error: " + str(msg)
    sys.stderr.write(msg.format(*args, **kwargs))
    raise SystemExit(kwargs.get("code", 1))


class PorkbunDDNS():
    def __init__(self, config, domain, subdomain=None, public_ips=None, fritzbox=None) -> None:
        with open(config) as fid:
            self.config = json.load(fid)
            required_keys = ["secretapikey", "apikey", "endpoint"]
            if all(x not in self.config for x in required_keys):
                err("all of the following are required in '{}': {}",
                    self.config, required_keys)

        if public_ips is None:
            if fritzbox:
                req = urllib.request.Request('http://' + fritzbox + ':49000/igdupnp/control/WANIPConn1')
                req.add_header('Content-Type', 'text/xml; charset="utf-8"')
                req.add_header('SOAPAction', 'urn:schemas-upnp-org:service:WANIPConnection:1#GetExternalIPAddress')
                data = '<?xml version="1.0" encoding="utf-8"?>' + \
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">' + \
                        '<s:Body>' + \
                            '<u:GetExternalIPAddress xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1" />' + \
                        '</s:Body>' + \
                    '</s:Envelope>'
                req.data =  data.encode('utf8')
                ipv4_address = ET.fromstring(urllib.request.urlopen(req).read()).find('.//NewExternalIPAddress').text

                req = urllib.request.Request('http://' + fritzbox + ':49000/igdupnp/control/WANIPConn1')
                req.add_header('Content-Type', 'text/xml; charset="utf-8"')
                req.add_header('SOAPAction', 'urn:schemas-upnp-org:service:WANIPConnection:1#X_AVM_DE_GetExternalIPv6Address')
                data = '<?xml version="1.0" encoding="utf-8"?>' + \
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">' + \
                        '<s:Body>' + \
                            '<u:X_AVM_DE_GetExternalIPv6Address xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1" />' + \
                        '</s:Body>' + \
                    '</s:Envelope>'
                req.data =  data.encode('utf8')
                ipv6_address = ET.fromstring(urllib.request.urlopen(req).read()).find('.//NewExternalIPv6Address').text
                public_ips = [ipv4_address, ipv6_address]
            else:
                public_ips = [urllib.request.urlopen('https://v4.ident.me').read().decode('utf8'),
                              urllib.request.urlopen('https://v6.ident.me').read().decode('utf8')]

        self.public_ips = [ipaddress.ip_address(x) for x in public_ips]

        self.domain = domain.lower()
        self.subdomain = subdomain.lower()
        self.fqdn = '.'.join([self.subdomain, self.domain])

        self.records = None
        self.get_records()

    def api(self, target, data=None) -> dict:
        data = data or self.config
        req = urllib.request.Request(self.config["endpoint"] + target,)
        req.data = json.dumps(data).encode('utf8')
        response = urllib.request.urlopen(req).read()
        return json.loads(response.decode('utf-8'))

    def get_records(self):
        records = self.api("/dns/retrieve/" + self.domain)
        if records["status"] == "ERROR":
            err(
                "Failed to get records. "
                "Make sure you specified the correct domain ({}), "
                "and that API access has been enabled for this domain.",
                self.domain,
            )
        else:
            self.records = records['records']

    def update_record(self):
        update_record = False
        domain_names = [x['name'] for x in self.records if x['type']
                        in ["A", "AAAA", "ALIAS", "CNAME"]]
        if self.fqdn in domain_names:
            for i in self.records:
                if i["name"] == self.fqdn and i["type"] in ["A", "AAAA", "ALIAS", "CNAME"]:
                    if i['content'] not in [x.exploded for x in self.public_ips]:
                        self.delete_record(i['id'])
                        update_record = True
                    else:
                        print('{} record of {} is up to date!'.format(
                            i["type"], i["name"]))
        else:
            update_record = True
            print('Adding new {} record for {}'.format(
                            i["type"], i["name"]))
        if update_record:
            self.create_record()
        return update_record

    def delete_record(self, domain_id):
        type, name, content = [(x['type'], x['name'], x['content']) for x in self.records if x['id'] == domain_id][0]
        print('Deleting {}-Record for {} with content: {}'.format(type, name, content))
        status = self.api("/dns/delete/" + self.domain + "/" + domain_id)
        print(status["status"])

    def create_record(self):
        for ip in self.public_ips:
            obj = self.config.copy()
            type_ = "A" if ip.version == 4 else "AAAA"
            obj.update({"name": self.subdomain, "type": type_,
                        "content": ip.exploded, "ttl": 300})
            print("Creating {}-Record for '{}' with content: '{}'".format(type_, self.fqdn, ip))
            status = self.api("/dns/create/" + self.domain, obj)
            print(status["status"])


def main(args):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("config",help="Path to config file")
    parser.add_argument("domain", help="Domain to be updated")

    subdomain = parser.add_mutually_exclusive_group()
    subdomain.add_argument('subdomain', nargs='?', default=None, help="Subdomain")

    public_ips = parser.add_mutually_exclusive_group()
    public_ips.add_argument('-i', '--public-ips', nargs='*', default=None, help="Public IPs (v4 and or v6)")

    fritzbox = parser.add_mutually_exclusive_group()
    fritzbox.add_argument('-f', '--fritzbox', default=None, help="IP or Domain of your Fritz!Box")

    args = parser.parse_args(args)

    porkbun_ddns = PorkbunDDNS(config=args.config, domain=args.domain,
                               subdomain=args.subdomain, public_ips=args.public_ips, fritzbox=args.fritzbox)
    porkbun_ddns.update_record()


if __name__ == "__main__":
    main(sys.argv[1:])
