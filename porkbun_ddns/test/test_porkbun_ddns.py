import unittest
from unittest.mock import patch
from ..porkbun_ddns import PorkbunDDNS, PorkbunDDNS_Error
import logging

logger = logging.getLogger('porkbun_ddns')
logger.setLevel(logging.INFO)


valid_config = {"endpoint": "https://porkbun.com/api/json/v3",
                "apikey": "pk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "secretapikey": "sk1_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                }

domain = 'my-domain.local'
ips = ['127.0.0.1', '::1']


def mock_api(status="SUCCESS", mock_records=None):
    records = list()
    if mock_records:
        mock_id = 1111111111
        for record in mock_records:
            records.append(
                {
                    "id": str(mock_id),
                    "name": record["name"],
                    "type": record["type"],
                    "content": record["content"],
                    "ttl": "600",
                    "prio": "0",
                    "notes": ""
                }
            )
            mock_id += 1
    return {"status": status, "records": records}


class TestPorkbunDDNS(unittest.TestCase):
    maxDiff = None

    def test_check_valid_config(self):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        self.assertEqual(porkbun_ddns.config, valid_config)
        valid_config_wo_endpoint = valid_config.copy()
        valid_config_wo_endpoint.pop('endpoint')
        porkbun_ddns = PorkbunDDNS(valid_config_wo_endpoint, domain, ips)
        self.assertEqual(porkbun_ddns.config, valid_config)

    def test_check_invalid_config(self):
        self.assertRaises(PorkbunDDNS_Error, PorkbunDDNS,
                          {'invalid': 000}, domain, ips)
        self.assertRaises(FileNotFoundError, PorkbunDDNS,
                          'invalid', domain, ips)
        self.assertRaises(TypeError, PorkbunDDNS, None, domain, ips)
        self.assertRaises(TypeError, PorkbunDDNS, 000, domain, ips)

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
                      status='SUCCESS',
                      mock_records=[
                          {
                              "name": "my-domain.local",
                              "type": "A",
                              "content": "127.0.0.1"},
                          {
                              "name": "my-domain.local",
                              "type": "AAAA",
                              "content": "0000:0000:0000:0000:0000:0000:0000:0001"}
                      ]))
    def test_record_exists_and_up_to_date(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs('porkbun_ddns', level='INFO') as cm:
            porkbun_ddns.set_subdomain('@')
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ['INFO:porkbun_ddns:A-Record of my-domain.local is up to date!',
                              'INFO:porkbun_ddns:AAAA-Record of my-domain.local is up to date!'])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
                      status='SUCCESS',
                      mock_records=[
                          {
                              "name": "my-domain.local",
                              "type": "A",
                              "content": "127.0.0.2"},
                          {
                              "name": "my-domain.local",
                              "type": "AAAA",
                              "content": "0000:0000:0000:0000:0000:0000:0000:0002"}
                      ]))
    def test_record_exists_and_out_dated(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs('porkbun_ddns', level='INFO') as cm:
            porkbun_ddns.set_subdomain('@')
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ['INFO:porkbun_ddns:Deleting A-Record for my-domain.local with content: '
                              '127.0.0.2, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: '
                              '127.0.0.1, Status: SUCCESS',
                              'INFO:porkbun_ddns:Deleting AAAA-Record for my-domain.local with content: '
                              '0000:0000:0000:0000:0000:0000:0000:0002, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: '
                              '0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS'])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api())
    def test_record_do_not_exists(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs('porkbun_ddns', level='INFO') as cm:
            porkbun_ddns.set_subdomain('@')
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ['INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: '
                              '127.0.0.1, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: '
                              '0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS'])

    @patch.object(PorkbunDDNS,
                  "_api",
                  return_value=mock_api(
                      status='SUCCESS',
                      mock_records=[
                          {
                              "name": "my-domain.local",
                              "type": "ALIAS",
                              "content": "my-domain.lan"
                          },
                          {
                              "name": "my-domain.local",
                              "type": "CNAME",
                              "content": "my-domain.lan"}
                      ]))
    def test_record_overwrite_alias_and_cname(self, mocker=None):
        porkbun_ddns = PorkbunDDNS(valid_config, domain, ips)
        with self.assertLogs('porkbun_ddns', level='INFO') as cm:
            porkbun_ddns.set_subdomain('@')
            porkbun_ddns.update_records()
            self.assertEqual(cm.output,
                             ['INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: '
                              'my-domain.lan, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: '
                              '127.0.0.1, Status: SUCCESS',
                              'INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: '
                              'my-domain.lan, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating A-Record for my-domain.local with content: '
                              '127.0.0.1, Status: SUCCESS',
                              'INFO:porkbun_ddns:Deleting ALIAS-Record for my-domain.local with content: '
                              'my-domain.lan, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: '
                              '0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS',
                              'INFO:porkbun_ddns:Deleting CNAME-Record for my-domain.local with content: '
                              'my-domain.lan, Status: SUCCESS',
                              'INFO:porkbun_ddns:Creating AAAA-Record for my-domain.local with content: '
                              '0000:0000:0000:0000:0000:0000:0000:0001, Status: SUCCESS'])


if __name__ == '__main__':
    unittest.main()
