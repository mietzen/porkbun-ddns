# Changelog

## [Unreleased]
### Added
- **Docker Secrets Support:** `entrypoint.py` now correctly reads `_FILE` environment variables, allowing API keys to be securely injected via Docker secrets.
- **Improved Configuration Handling:** `entrypoint.py` now uses `get_secret_from_env()` to correctly retrieve API keys from either environment variables or secret files.
