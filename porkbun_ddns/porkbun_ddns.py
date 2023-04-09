import json
import sys
import ipaddress
import urllib.request
from .helpers import get_ips_from_fritzbox


def err(msg, *args, **kwargs):
    msg = "Error: " + str(msg)
    sys.stderr.write(msg.format(*args, **kwargs))
    raise SystemExit(kwargs.get("code", 1))


class PorkbunDDNS():
    """A class for updating dynamic DNS records for a Porkbun domain.

    Returns:
        None
    """

    def __init__(self, config, domain, subdomain=None, public_ips=None, fritzbox_ip=None, ipv4=True, ipv6=True) -> None:
        self._load_config(config)
        self.public_ips = public_ips
        if self.public_ips is None:
            self.public_ips = self.get_public_ips(fritzbox_ip, ipv4, ipv6)
        self.domain = domain.lower()
        self.subdomain = subdomain.lower()
        self.fqdn = '.'.join([self.subdomain, self.domain])
        self.records = self.get_records()

    def _load_config(self, config: str):
        """Load a JSON configuration file and validate its contents.

        Args:
            config (str): The name of the configuration file to be loaded.

        Raises:
            ValueError: If any of the required keys are missing from the loaded JSON file.
        """
        with open(config) as fid:
            self.config = json.load(fid)
            required_keys = ["secretapikey", "apikey", "endpoint"]
            if all(x not in self.config for x in required_keys):
                err("all of the following are required in '{}': {}",
                    self.config, required_keys)

    def get_public_ips(self, fritzbox_ip=None, ipv4=True, ipv6=True):
        """Retrieve the public IP addresses of the network.

        This method retrieves the public IP addresses of the network either from a FritzBox router or by querying a public service for IPv4 and/or IPv6 addresses.
        The IP addresses are returned as a list of `ipaddress.ip_address` objects.

        Args:
            fritzbox_ip (str, optional): The IP address of the FritzBox router. If not specified, the public IP addresses are retrieved from public services. Default is None.
            ipv4 (bool, optional): Whether to retrieve the IPv4 address. Default is True.
            ipv6 (bool, optional): Whether to retrieve the IPv6 address. Default is True.

        Returns:
            list: A list of `ipaddress.ip_address` objects representing the public IP addresses of the network.

        Raises:
            ValueError: If both `ipv4` and `ipv6` are False or if none of the public services return IP addresses.
        """
        public_ips = []
        if fritzbox_ip:
            if ipv4:
                public_ips.append(
                    get_ips_from_fritzbox(fritzbox_ip, ipv4=True))
            if ipv6:
                public_ips.append(get_ips_from_fritzbox(
                    fritzbox_ip, ipv4=False))
        else:
            if ipv4:
                public_ips.append(urllib.request.urlopen(
                    'https://v4.ident.me').read().decode('utf8'))
            if ipv6:
                public_ips.append(urllib.request.urlopen(
                    'https://v6.ident.me').read().decode('utf8'))
        public_ips = set(public_ips)

        if not public_ips:
            err('Failed to obtain IP Addresses!')

        return [ipaddress.ip_address(x) for x in public_ips]

    def api(self, target, data=None) -> dict:
        """Send an API request to a specified target.

        This method sends an API request to a target URL with optional data in the request body, using the endpoint specified in the loaded configuration.
        The response from the API is returned as a dictionary.

        Args:
            target (str): The URL path to send the API request to.
            data (dict, optional): The data to include in the request body. If not specified, the data from the loaded configuration is used. Default is None.

        Returns:
            dict: A dictionary containing the response from the API.

        Raises:
            urllib.error.URLError: If there is an error with the API request or if the API response is not valid JSON.
        """

        data = data or self.config
        req = urllib.request.Request(self.config['endpoint'] + target,)
        req.data = json.dumps(data).encode('utf8')
        response = urllib.request.urlopen(req).read()
        return json.loads(response.decode('utf-8'))

    def get_records(self):
        """Retrieve the DNS records for the specified domain.

        This method retrieves the DNS records for the domain specified during initialization, using the API method `"/dns/retrieve/<domain>"`.
        The method returns the list of records if the API response status is "SUCCESS".
        If the API response status is not "SUCCESS", an error is raised.

        Returns:
            list: A list of DNS records for the specified domain.

        Raises:
            ValueError: If the API response status is not "SUCCESS".
        """

        records = self.api("/dns/retrieve/" + self.domain)
        if records["status"] == "SUCCESS":
            return records['records']
        else:
            err(
                "Failed to get records. "
                "Make sure you specified the correct domain ({}), "
                "and that API access has been enabled for this domain.",
                self.domain,
            )

    def update_records(self):
        """Update DNS records for the specified domain.

        This method updates the DNS records for the domain specified during initialization using the API methods `_delete_record` and `_create_records`. The method first retrieves the domain names of all records of type A, AAAA, ALIAS, and CNAME. It then iterates over the list of public IP addresses and determines whether the records for the specified domain need to be updated, created, or deleted. The method logs a message if a record is up to date.

        Returns:
            None
        """

        domain_names = [x['name'] for x in self.records if x['type']
                        in ["A", "AAAA", "ALIAS", "CNAME"]]
        for ip in self.public_ips:
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
                        if i["type"] != record_type and record_type not in [x['type'] for x in self.records if x['name'] == self.fqdn]:
                            self._create_records(ip, record_type)
                        # Everything is up to date
                        if i["type"] == record_type and i['content'] == ip.exploded:
                            print('{}-Record of {} is up to date!'.format(
                                i["type"], i["name"]))
            else:
                # Create new record
                self._create_records(ip, record_type)

    def _delete_record(self, domain_id):
        """Delete a DNS record with the given domain ID.

        Args:
            domain_id (str): The ID of the DNS record to delete.

        Returns:
            None
        """

        type, name, content = [(x['type'], x['name'], x['content'])
                               for x in self.records if x['id'] == domain_id][0]
        status = self.api("/dns/delete/" + self.domain + "/" + domain_id)
        print('Deleting {}-Record for {} with content: {}, Status: {}'.format(type,
              name, content, status["status"]))

    def _create_records(self, ip, record_type):
        """Create DNS records for the subdomain with the given IP address and type.

        Args:
            ip (ipaddress.IPv4Address or ipaddress.IPv6Address): The IP address to use for
                the new DNS record.
            record_type (str): The type of the new DNS record, such as "A" or "AAAA" record.

        Returns:
            None
        """

        obj = self.config.copy()
        obj.update({"name": self.subdomain, "type": record_type,
                    "content": ip.exploded, "ttl": 600})
        status = self.api("/dns/create/" + self.domain, obj)
        print('Creating {}-Record for {} with content: {}, Status: {}'.format(record_type,
              self.fqdn, ip.exploded, status["status"]))
