from __future__ import annotations

import logging
import json
import ipaddress
import urllib.request
from .helpers import get_ips_from_fritzbox

logger = logging.getLogger('porkbun_ddns')

class PorkbunDDNS_Error(Exception):
    pass


class PorkbunDDNS():
    """A class for updating dynamic DNS records for a Porkbun domain.
    """

    def __init__(
        self,
        config: dict | str,
        domain: str,
        public_ips: list | None = None,
        fritzbox_ip: str | None = None,
        ipv4: bool = True,
        ipv6: bool = True
    ) -> None:
        if isinstance(config, dict):
            self.config = config
        else:
            if isinstance(config, str):
                try:
                    self._load_config(config)
                except FileNotFoundError as err:
                    raise FileNotFoundError("Config path is invalid!\nPath:\n{}".format(config)) from err
            else:
                raise TypeError("Invalid config! Config should be a str (filepath) or dict!\nYour config:\n{}\nType: {}".format(
                config, type(config)))

        self._check_config()
        self.static_ips = public_ips
        self.domain = domain.lower()
        self.records = None
        self.fritzbox_ip = fritzbox_ip
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.fqdn = self.domain
        self.subdomain = '@'

    def _load_config(self, config: str) -> None:
        """Load a JSON configuration file.
        """
        with open(config) as fid:
            self.config = json.load(fid)

    def _check_config(self) -> None:
        """Check if the configuration is valid.
        """
        required_keys = ["secretapikey", "apikey"]
        if all(x not in self.config for x in required_keys):
            raise PorkbunDDNS_Error("Missing keys! All of the following are required: '{}'\nYour config:\n{}".format(
                required_keys, self.config))
        if 'endpoint' not in self.config.keys():
            self.config["endpoint"] = "https://porkbun.com/api/json/v3"

    def set_subdomain(self, subdomain: str) -> None:
        self.subdomain = subdomain.lower()
        if self.subdomain != '@':
            self.fqdn = '.'.join([self.subdomain, self.domain])

    def get_public_ips(self) -> list:
        """Retrieve the public IP addresses of the network.
        """
        if self.static_ips:
            public_ips = self.static_ips
        else:
            public_ips = []
            if self.fritzbox_ip:
                if self.ipv4:
                    public_ips.append(
                        get_ips_from_fritzbox(self.fritzbox_ip, ipv4=True))
                if self.ipv6:
                    public_ips.append(get_ips_from_fritzbox(
                        self.fritzbox_ip, ipv4=False))
            else:
                if self.ipv4:
                    public_ips.append(urllib.request.urlopen(
                        'https://v4.ident.me').read().decode('utf8'))
                if self.ipv6:
                    public_ips.append(urllib.request.urlopen(
                        'https://v6.ident.me').read().decode('utf8'))
            public_ips = set(public_ips)

        if not public_ips:
            raise PorkbunDDNS_Error('Failed to obtain IP Addresses!')

        return [ipaddress.ip_address(x) for x in public_ips]

    def _api(self, target: str, data: dict = None) -> dict:
        """Send an API request to a specified target.
        """

        data = data or self.config
        req = urllib.request.Request(self.config['endpoint'] + target)
        req.data = json.dumps(data).encode('utf8')
        response = urllib.request.urlopen(req).read()
        return json.loads(response.decode('utf-8'))

    def get_records(self) -> dict:
        """Retrieve the DNS records for the specified domain.
        """

        records = self._api("/dns/retrieve/" + self.domain)
        if records["status"] == "SUCCESS":
            return records['records']
        else:
            raise PorkbunDDNS_Error(
                'Failed to get records.\n' +
                'Make sure you specified the correct domain ({}),\n'.format(self.domain) +
                'and that API access has been enabled for this domain.'
            )

    def update_records(self):
        """Update DNS records for the specified domain.
        """
        self.records = self.get_records()
        domain_names = [x['name'] for x in self.records if x['type']
                        in ["A", "AAAA", "ALIAS", "CNAME"]]
        for ip in self.get_public_ips():
            record_type = "A" if ip.version == 4 else "AAAA"
            if self.fqdn in domain_names:
                for i in self.records:
                    if i["name"] == self.fqdn:
                        # Overwrite ALIAS and CNAME
                        if i["type"] in ["ALIAS", "CNAME"]:
                            self._delete_record(i['id'])
                            self._create_records(ip, record_type)
                        # Update existing entry
                        if i["type"] == record_type and i['content'] != ip.exploded:
                            self._delete_record(i['id'])
                            self._create_records(ip, record_type)
                        # Create missing A or AAAA entry
                        if i["type"] not in ["ALIAS", "CNAME", record_type] and record_type not in [x['type'] for x in self.records if x['name'] == self.fqdn]:
                            self._create_records(ip, record_type)
                        # Everything is up to date
                        if i["type"] == record_type and i['content'] == ip.exploded:
                            logger.info('{}-Record of {} is up to date!'.format(
                                i["type"], i["name"]))
            else:
                # Create new record
                self._create_records(ip, record_type)

    def _delete_record(self, domain_id: str):
        """Delete a DNS record with the given domain ID.
        """

        type, name, content = [(x['type'], x['name'], x['content'])
                               for x in self.records if x['id'] == domain_id][0]
        status = self._api("/dns/delete/" + self.domain + "/" + domain_id)
        logger.info('Deleting {}-Record for {} with content: {}, Status: {}'.format(type,
              name, content, status["status"]))

    def _create_records(self, ip: ipaddress, record_type: str):
        """Create DNS records for the subdomain with the given IP address and type.
        """

        data = self.config.copy()
        data.update({"name": self.subdomain, "type": record_type,
                    "content": ip.exploded, "ttl": 600})
        status = self._api("/dns/create/" + self.domain, data)
        logger.info('Creating {}-Record for {} with content: {}, Status: {}'.format(record_type,
              self.fqdn, ip.exploded, status["status"]))
