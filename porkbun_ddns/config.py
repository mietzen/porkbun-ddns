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
    """Returns the default path for the config file."""
    return xdg.xdg_config_home() / "porkbun-ddns-config.json"

def create_default_config_file():
    """Creates a default configuration file if one does not exist."""
    config_file_path = get_config_file_default()
    if not config_file_path.is_file():
        config_file_path.parent.mkdir(parents=True, exist_ok=True)
        config_file_path.write_text(config_file_default_content)
        logger.info("Wrote default config to: %s", config_file_path)

def load_config_file(config_file: Path | None) -> dict[str, str] | None:
    """Loads the config file, if available."""
    if config_file and config_file.is_file():
        with open(config_file, "r") as cf:
            config = json.load(cf)
            if "apikey" not in config or "secretapikey" not in config:
                raise ValueError("Config file must include 'apikey' and 'secretapikey'")
            return config
    return None

def get_secret_from_env(env_name: str) -> str | None:
    """Retrieve the API key from environment variable or a file specified in an `_FILE` env variable."""
    file_var = f"{env_name}_FILE"
    if file_var in os.environ:
        try:
            with open(os.environ[file_var], "r") as file:
                return file.read().strip()
        except Exception as e:
            logger.error(f"Error reading secret from {file_var}: {e}")
            return None
    return os.environ.get(env_name)  # Fall back to normal environment variable

class Config(NamedTuple):
    """Configuration object storing endpoint, API key, and secret API key."""
    endpoint: str
    apikey: str
    secretapikey: str

    @staticmethod
    def from_env_or_config(config_file: Path | None = None) -> "Config":
        """Loads configuration from environment variables, Docker secrets, or a config file."""

        # 1. Try to get API keys from secrets (_FILE env variables)
        apikey = get_secret_from_env("APIKEY")
        secretapikey = get_secret_from_env("SECRETAPIKEY")

        # 2. If API keys were not set via secrets, try the config file
        config = load_config_file(config_file) if not apikey or not secretapikey else None
        apikey = apikey or (config.get("apikey", "") if config else "")
        secretapikey = secretapikey or (config.get("secretapikey", "") if config else "")

        if not apikey or not secretapikey:
            raise RuntimeError("Missing API keys! Set them via secrets, environment variables, or a config file.")

        return Config(
            endpoint=config.get("endpoint", DEFAULT_ENDPOINT) if config else DEFAULT_ENDPOINT,
            apikey=apikey,
            secretapikey=secretapikey,
        )

