import argparse
import json
import logging
import os
from pathlib import Path
from typing import Final, NamedTuple

import xdg_base_dirs as xdg

from porkbun_ddns.errors import PorkbunDDNS_Error

logger = logging.getLogger("porkbun_ddns")

DEFAULT_ENDPOINT: Final = "https://api.porkbun.com/api/json/v3"

config_file_default_content: Final = \
    f"""
{{
    "endpoint": "{DEFAULT_ENDPOINT}",
    "apikey": "",
    "secretapikey": ""
}}
"""

def get_config_file_default() -> Path:
    return xdg.xdg_config_home() / "porkbun-ddns-config.json"

def create_default_config_file():
    if not xdg.xdg_config_home().is_dir():
        os.makedirs(xdg.xdg_config_home())
        logger.info("Generating config home: %s", xdg.xdg_config_home())

    config_file_path = get_config_file_default()
    if not config_file_path.is_file():
        config_file_path.write_text(config_file_default_content)
        logger.info("Wrote config to: %s", config_file_path)

def load_config_file(config_file: Path | None) -> dict[str, str] | None:
    config = None
    if config_file:
        if not config_file.is_file():
            raise ValueError("Not a file: %s", config_file)
        with config_file.open() as cf:
            config = json.load(cf)
            logger.debug("Loaded config from: %s", config_file)
            required_keys = ["secretapikey", "apikey"]
            if all(x not in config for x in required_keys):
                raise PorkbunDDNS_Error(f"Missing keys! All of the following are required: \
                    '{required_keys}'\nYour config:\n{config}")
    return config


class Credentials(NamedTuple):
    apikey: str
    secretapikey: str
    endpoint: str = DEFAULT_ENDPOINT


class RetryPolicy(NamedTuple):
    retry_count: int = 3
    retry_delay: int = 5


class WebhookConfig(NamedTuple):
    webhook_url: str = ""
    webhook_template: str = ""
    webhook_template_file: str = ""


class AppConfig(NamedTuple):
    credentials: Credentials
    retry: RetryPolicy
    webhook: WebhookConfig


_LEAF_FIELDS: Final = (
    "apikey", "secretapikey", "endpoint",
    "retry_count", "retry_delay",
    "webhook_url", "webhook_template", "webhook_template_file",
)

_LEAF_DEFAULTS: Final = {
    "endpoint": DEFAULT_ENDPOINT,
    "retry_count": "3",
    "retry_delay": "5",
    "webhook_url": "",
    "webhook_template": "",
    "webhook_template_file": "",
}


class _Config:

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.config_file_path = None
        self.config_file_content = None
        if config_file := getattr(args, "config", None):
            self.config_file_path = Path(config_file)
            self.config_file_content = load_config_file(self.config_file_path)
        else:
            logger.debug("Skiped loading config file")
        self.options = {name: self._get_option_value(
            name) for name in _LEAF_FIELDS}

    def get_options(self) -> AppConfig:
        return AppConfig(
            credentials=Credentials(
                apikey=self.options["apikey"],
                secretapikey=self.options["secretapikey"],
                endpoint=self.options["endpoint"],
            ),
            retry=RetryPolicy(
                retry_count=int(self.options["retry_count"]),
                retry_delay=int(self.options["retry_delay"]),
            ),
            webhook=WebhookConfig(
                webhook_url=self.options["webhook_url"],
                webhook_template=self.options["webhook_template"],
                webhook_template_file=self.options["webhook_template_file"],
            ),
        )

    def _get_option_value(self, option_name: str) -> str:
        """Tries to get a value for the option_name from the program-arguments first,
        then from the environment-variables second and last from the config-file.
        Raises ValueError if nothing is found
        """
        if param := getattr(self.args, option_name, None):
            return str(param)
        env_option_name = "PORKBUN_" + option_name.upper()
        if param := os.environ.get(env_option_name, None):
            return str(param)
        if self.config_file_content and (param := self.config_file_content.get(option_name, None)):
            return str(param)
        if option_name in _LEAF_DEFAULTS:
            return _LEAF_DEFAULTS[option_name]
        raise PorkbunDDNS_Error(
            f"'{option_name}' is not defined via CLI-arguments,"
            f" as an environment-variable"
            f" nor in the config-file ("
            f"{self.config_file_path if self.config_file_path else 'no config-file defined'}"
            f")",
        )


def extract_config(extract_from: argparse.Namespace | Path) -> AppConfig:
    """Extracts an AppConfig-object, either from an argparse-Namespace or from a Path to a config-file"""
    if isinstance(extract_from, argparse.Namespace):
        return _Config(extract_from).get_options()
    if isinstance(extract_from, Path):
        if content := load_config_file(extract_from):
            return AppConfig(
                credentials=Credentials(
                    apikey=content.get("apikey", ""),
                    secretapikey=content.get("secretapikey", ""),
                    endpoint=content.get("endpoint", DEFAULT_ENDPOINT),
                ),
                retry=RetryPolicy(
                    retry_count=int(content.get("retry_count", 3)),
                    retry_delay=int(content.get("retry_delay", 5)),
                ),
                webhook=WebhookConfig(
                    webhook_url=content.get("webhook_url", ""),
                    webhook_template=content.get("webhook_template", ""),
                    webhook_template_file=content.get("webhook_template_file", ""),
                ),
            )
        raise ValueError(f"Not a file: {extract_from}")
    raise TypeError(f"{extract_from} is of type \
        {type(extract_from)}, not Namespace/Path")
