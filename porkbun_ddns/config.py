import argparse
import json
import logging
import os
from pathlib import Path
from typing import Final, NamedTuple, Optional, Union

import xdg

logger = logging.getLogger('porkbun_ddns')

DEFAULT_ENDPOINT: Final = "https://porkbun.com/api/json/v3"

config_file_default_content: Final = \
    f"""
{{
    "endpoint": "{DEFAULT_ENDPOINT}",
    "apikey": "pk1_xxx",
    "secretapikey": "sk1_xxx"
}}
"""


def get_config_file_default() -> Path:
    if not xdg.xdg_config_home().is_dir():
        os.makedirs(xdg.xdg_config_home())

    config_file_name = "porkbun-ddns-config.json"
    config_file_path = xdg.xdg_config_home() / config_file_name
    if not config_file_path.is_file():
        config_file_path.write_text(config_file_default_content)
    return config_file_path


def load_config_file(config_file: Optional[Path]) -> Optional[dict[str, str]]:
    if config_file:
        if not config_file.is_file():
            raise ValueError("Not a file: %s", config_file)
        with config_file.open() as cf:
            return json.load(cf)
    return None


class Config(NamedTuple):
    endpoint: str
    apikey: str
    secretapikey: str


class _Config:

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.config_file_path = None
        self.config_file_content = None
        if config_file := getattr(args, "config", None):
            self.config_file_path = Path(config_file)
            self.config_file_content = load_config_file(self.config_file_path)

        self.options = {name: self._get_option_value(name) for name in Config._fields}

    def get_options(self) -> Config:
        return Config(**self.options)

    def _get_option_value(self, option_name: str) -> str:
        """
        Tries to get a value for the option_name from the program-arguments first,
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
        raise ValueError(
            f"'{option_name}' is not defined via CLI-arguments,"
            f" as an environment-variable"
            f" nor in the config-file ("
            f"{self.config_file_path if self.config_file_path else 'no config-file defined'}"
            f")"
        )

# TODO: This needs rework:
def extract_config(extract_from: Union[argparse.Namespace, Path]) -> Config:
    """Extracts a Config-object, either from an argparse-Namespace or from  a Path to a config-file"""
    if isinstance(extract_from, argparse.Namespace):
        return _Config(extract_from).get_options()
    if isinstance(extract_from, Path):
        if content := load_config_file(extract_from):
            return Config(**content)
        raise ValueError(f"Not a file: {extract_from}")
    raise TypeError(f"{extract_from} is of type {type(extract_from)}, not Namespace/Path")
