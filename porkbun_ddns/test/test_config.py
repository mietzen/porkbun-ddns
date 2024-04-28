import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from porkbun_ddns.config import Config, extract_config, load_config_file
from porkbun_ddns.test.test_porkbun_ddns import valid_config
from porkbun_ddns.errors import PorkbunDDNS_Error

def _mock(*names_contained: str, key_pref: str = "", val_pref: str = "") -> dict[str, str]:
    d = valid_config._asdict()
    if names_contained:
        for name in names_contained:
            if name not in d:
                raise ValueError(f"{name} is not a config-value")
    else:
        names_contained = tuple(d.keys())
    d = {key_pref + key: val_pref + value for key, value in d.items() if key in names_contained}
    return d


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

    @patch.dict(os.environ, mock_environ())
    def test_all_argparse(self):
        config = extract_config(mock_namespace(self.mock_file()))
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("argparse_"))

    def test_all_argparse_no_env(self):
        config = extract_config(mock_namespace(self.mock_file()))
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("argparse_"))

        config = extract_config(mock_namespace())
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("argparse_"))

    @patch.dict(os.environ, mock_environ())
    def test_all_environ(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("environ_"))

        args = argparse.Namespace()
        config = extract_config(args)
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("environ_"))

    def test_all_file(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)
        for field in Config._fields:
            self.assertTrue(getattr(config, field).startswith("file_"))

    def test_not_set(self):
        args = argparse.Namespace()
        with self.assertRaises(PorkbunDDNS_Error):
            extract_config(args)

        args = mock_namespace(self.mock_file("apikey"), "secretapikey")
        with self.assertRaises(PorkbunDDNS_Error):
            extract_config(args)

    @patch.dict(os.environ, mock_environ())
    def test_mix_argparse_environ(self):
        args = mock_namespace(self.mock_file(), "endpoint")
        config = extract_config(args)

        self.assertTrue(config.endpoint.startswith("argparse_"))
        self.assertTrue(config.apikey.startswith("environ_"))
        self.assertTrue(config.secretapikey.startswith("environ_"))

    def test_mix_argparse_file(self):
        args = mock_namespace(self.mock_file(), "apikey")
        config = extract_config(args)

        self.assertTrue(config.endpoint.startswith("file_"))
        self.assertTrue(config.apikey.startswith("argparse_"))
        self.assertTrue(config.secretapikey.startswith("file_"))

    @patch.dict(os.environ, mock_environ("secretapikey"))
    def test_mix_environ_file(self):
        args = argparse.Namespace(config=self.mock_file())
        config = extract_config(args)

        self.assertTrue(config.endpoint.startswith("file_"))
        self.assertTrue(config.apikey.startswith("file_"))
        self.assertTrue(config.secretapikey.startswith("environ_"))

    def test_load_config_file(self):
        file = self.mock_file("endpoint", "secretapikey")
        d = load_config_file(file)

        self.assertTrue(d["endpoint"].startswith("file_"))
        self.assertTrue(d["secretapikey"].startswith("file_"))
        self.assertFalse("apikey" in d)

    def test_only_config_file(self):
        file = self.mock_file()
        config = extract_config(file)
        self.assertTrue(config.endpoint.startswith("file_"))
        self.assertTrue(config.apikey.startswith("file_"))
        self.assertTrue(config.secretapikey.startswith("file_"))


if __name__ == "__main__":
    unittest.main()
