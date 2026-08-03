import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from porkbun_ddns.config import (
    AppConfig,
    Credentials,
    RetryPolicy,
    WebhookConfig,
    extract_config,
    load_config_file,
)
from porkbun_ddns.errors import PorkbunDDNS_Error
from porkbun_ddns.test.test_porkbun_ddns import valid_config

LEAF_FIELDS = ("apikey", "secretapikey", "endpoint",
               "retry_count", "retry_delay",
               "webhook_url", "webhook_template", "webhook_template_file")

RETRY_FIELDS = ("retry_count", "retry_delay")

# Retry fields are int; encode the source as a distinct value per source.
RETRY_SOURCE_NUM = {"argparse_": 1, "environ_": 2, "file_": 3}


def _flat_leaf() -> dict[str, str]:
    return {
        **valid_config.credentials._asdict(),
        **valid_config.retry._asdict(),
        **valid_config.webhook._asdict(),
    }


def _leaf_value(config: AppConfig, field: str):
    if field in Credentials._fields:
        return getattr(config.credentials, field)
    if field in RetryPolicy._fields:
        return getattr(config.retry, field)
    if field in WebhookConfig._fields:
        return getattr(config.webhook, field)
    raise ValueError(f"{field} is not a config-value")


def _mock(*names_contained: str, key_pref: str = "", val_pref: str = "") -> dict[str, str]:
    d = _flat_leaf()
    if names_contained:
        for name in names_contained:
            if name not in d:
                raise ValueError(f"{name} is not a config-value")
    else:
        names_contained = tuple(d.keys())
    result = {}
    for key, value in d.items():
        if key not in names_contained:
            continue
        if key in RETRY_FIELDS:
            result[key_pref + key] = str(RETRY_SOURCE_NUM[val_pref])
        else:
            result[key_pref + key] = val_pref + str(value)
    return result


def mock_namespace(config_file: Path | None = None, *names_contained: str) -> argparse.Namespace:
    d = _mock(*names_contained, val_pref="argparse_")
    if config_file:
        d |= {"config": str(config_file)}
    return argparse.Namespace(**d)


def mock_environ(*names_contained: str) -> dict[str, str]:
    d = _mock(*names_contained, key_pref="porkbun_", val_pref="environ_")
    return {key.upper(): value for key, value in d.items()}


class TestConfig(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmpdir = None

    def mock_file(self, *names_contained: str) -> Path:
        d = _mock(*names_contained, val_pref="file_")
        self.tmpdir = tempfile.TemporaryDirectory()
        tmpfile = Path(self.tmpdir.name) / "porkbun-ddns-config.json"
        with tmpfile.open(mode="w") as tf:
            json.dump(d, tf)
        return tmpfile

    def tearDown(self) -> None:
        if self.tmpdir:
            self.tmpdir.cleanup()
            self.tmpdir = None

    def assert_source(self, config: AppConfig, val_pref: str) -> None:
        for field in LEAF_FIELDS:
            value = _leaf_value(config, field)
            if field in RETRY_FIELDS:
                self.assertEqual(value, RETRY_SOURCE_NUM[val_pref])
            else:
                self.assertTrue(value.startswith(val_pref))

    @patch.dict(os.environ, mock_environ())
    def test_all_argparse(self):
        config = extract_config(mock_namespace(self.mock_file()))
        self.assert_source(config, "argparse_")

    def test_all_argparse_no_env(self):
        config = extract_config(mock_namespace(self.mock_file()))
        self.assert_source(config, "argparse_")

        config = extract_config(mock_namespace())
        self.assert_source(config, "argparse_")

    @patch.dict(os.environ, mock_environ())
    def test_all_environ(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)
        self.assert_source(config, "environ_")

        args = argparse.Namespace()
        config = extract_config(args)
        self.assert_source(config, "environ_")

    def test_all_file(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)
        self.assert_source(config, "file_")

    def test_not_set(self):
        args = argparse.Namespace()
        with self.assertRaises(PorkbunDDNS_Error):
            extract_config(args)

        args = mock_namespace(self.mock_file("secretapikey"), "secretapikey")
        with self.assertRaises(PorkbunDDNS_Error):
            extract_config(args)

    @patch.dict(os.environ, mock_environ())
    def test_mix_argparse_environ(self):
        args = mock_namespace(self.mock_file(), "endpoint")
        config = extract_config(args)

        self.assertTrue(config.credentials.endpoint.startswith("argparse_"))
        self.assertTrue(config.credentials.apikey.startswith("environ_"))
        self.assertTrue(config.credentials.secretapikey.startswith("environ_"))

    def test_mix_argparse_file(self):
        args = mock_namespace(self.mock_file(), "apikey")
        config = extract_config(args)

        self.assertTrue(config.credentials.endpoint.startswith("file_"))
        self.assertTrue(config.credentials.apikey.startswith("argparse_"))
        self.assertTrue(config.credentials.secretapikey.startswith("file_"))

    @patch.dict(os.environ, mock_environ("secretapikey"))
    def test_mix_environ_file(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)

        self.assertTrue(config.credentials.endpoint.startswith("file_"))
        self.assertTrue(config.credentials.apikey.startswith("file_"))
        self.assertTrue(config.credentials.secretapikey.startswith("environ_"))

    def test_load_config_file(self):
        file = self.mock_file("endpoint", "secretapikey")
        d = load_config_file(file)

        self.assertTrue(d["endpoint"].startswith("file_"))
        self.assertTrue(d["secretapikey"].startswith("file_"))
        self.assertFalse("apikey" in d)

    def test_only_config_file(self):
        file = self.mock_file()
        config = extract_config(file)
        self.assertTrue(config.credentials.endpoint.startswith("file_"))
        self.assertTrue(config.credentials.apikey.startswith("file_"))
        self.assertTrue(config.credentials.secretapikey.startswith("file_"))


if __name__ == "__main__":
    unittest.main()
