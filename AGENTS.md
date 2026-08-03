# AGENTS.md

## Project Overview

porkbun-ddns is an unofficial DDNS client for Porkbun domains. Distributed as both a pip package (`porkbun-ddns` on PyPI) and a Docker image (`porkbun-ddns` on Docker Hub). Sets/updates A (IPv4) and AAAA (IPv6) DNS records, only updating when IPs change.

- **Language:** Python 3.10+
- **Build system:** setuptools (version injected via `VERSION` env var in `setup.py`)
- **License:** MIT

## Repository Structure

```
porkbun_ddns/            # Python package
├── __init__.py          # Package init, exports PorkbunDDNS class
├── porkbun_ddns.py      # Core DDNS logic (orchestrator)
├── cli.py               # CLI entry point (porkbun-ddns command)
├── config.py            # Configuration handling (AppConfig, Credentials, RetryPolicy, WebhookConfig)
├── api.py               # PorkbunAPIClient (HTTP API wrapper)
├── reconcile.py         # Reconciliation logic (reconcile + Ensure intents)
├── resolver.py          # PublicIPResolver (public IP discovery)
├── helpers.py           # Utility functions
├── webhook.py           # Jinja-templated webhook delivery
├── errors.py            # Custom exceptions
├── scripts/             # Console-script entry points
│   └── fritzbox_ips.py  # fritzbox-ips sidecar (obtains public IPs from Fritz!Box)
└── test/                # pytest unit tests

Docker/
├── Dockerfile           # Multi-arch image (python:3.14-slim base)
├── entrypoint.py        # Docker-specific entry point (env var config)
├── docker-compose.yml   # Example compose file
└── test/
    ├── test.sh          # Docker test runner
    └── integration/     # cinc-auditor (inspec) integration tests

.github/
├── dependabot.yml       # Dependabot config (docker, github-actions, pip)
├── platforms.json       # Docker build target platforms
├── workflows/           # GitHub Actions (see CI/CD section)
└── ISSUE_TEMPLATE/      # Bug report, feature request, question templates
```

## CI/CD Architecture

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `lint_and_test.yml` | PR to main | pytest across Python 3.10-3.14 + ruff linting |
| `auto-merge-dependabot.yml` | Schedule (every 6h) + manual | Enables auto-merge via GitHub App token. 14-day cooldown for python PRs (requirements.txt / pyproject.toml / setup.py); docker and github-actions PRs auto-merge on next schedule tick |
| `auto-release.yml` | Merged dependabot python PR | Patch-bumps version and creates a new GitHub release |
| `docker-rebuild.yml` | Merged dependabot docker PR / workflow_dispatch | Rebuild Docker images at current version (no new release) |
| `docker.yml` | GitHub release published / PR | Build multi-arch Docker images, push to Docker Hub on release |
| `pypi.yml` | GitHub release published | Build wheel, publish to PyPI (trusted publisher) |
| `feedback-label.yml` | Issue comment | Manage "Feedback needed" label on issues |

### Dependabot

Watches three ecosystems:
- **docker** (`/Docker`): Python base image, patch updates only
- **github-actions** (`/.github/workflows`): All action version updates
- **pip** (`/`): Python dependency updates

### Release Process

**Python dependabot bumps** (automated):
1. Dependabot opens PR for Python dependency update
2. `lint_and_test.yml` runs PR checks
3. `auto-merge-dependabot.yml` waits for the PR to be at least 14 days old, then enables auto-merge (supply-chain defense)
4. On merge, `auto-release.yml` patch-bumps the version (e.g. `v1.1.27` → `v1.1.28`) and creates a GitHub release
5. `pypi.yml` publishes the new wheel to PyPI, `docker.yml` builds multi-arch Docker images with the new version tags

**Docker dependabot bumps** (automated):
1. Dependabot opens PR for Docker base image update
2. `auto-merge-dependabot.yml` enables auto-merge on the next schedule tick
3. On merge, `docker-rebuild.yml` rebuilds Docker images at current version
4. Overwrites existing version tags and `latest` — no new release, no PyPI publish

**New feature/bugfix release** (manual):
1. Developer creates GitHub release with `vX.Y.Z` tag
2. `pypi.yml` builds and publishes wheel to PyPI
3. `docker.yml` builds multi-arch Docker images with new version tags

**Version format:** `vX.Y.Z` tag → `X.Y.Z` used for PyPI version and Docker tags

### Docker Build

- **Platforms:** linux/amd64, linux/arm64, linux/arm/v7, linux/arm/v6 (defined in `.github/platforms.json`)
- **Tags per arch:** `{version}-{arch}-{build_nr}`, `{version}-{arch}`, `{arch}`
- **Shared manifests:** `{version}`, `latest`
- **Testing:** cinc-auditor (inspec) integration tests run against each arch build

## Testing

### Python Tests
```bash
# Unit tests
pytest ./porkbun_ddns/test

# Linting
ruff check --ignore=E501 --exclude=__init__.py ./porkbun_ddns
```

### Docker Tests
Docker integration tests use cinc-auditor (inspec) and run automatically in CI. Located in `Docker/test/integration/`.

## Coding Conventions

- **Version:** Dynamic via `VERSION` env var in `setup.py` — never hardcoded
- **Dependencies:** `xdg-base-dirs~=6.0.2` (pinned minor), `jinja2` (webhook templating)
- **CLI entry points:** `porkbun-ddns` → `porkbun_ddns.cli:main`, `fritzbox-ips` → `porkbun_ddns.scripts.fritzbox_ips:main`
- **Docker entry point:** `/entrypoint.py` — all config via environment variables:
  - Required: `DOMAIN`, `APIKEY`, `SECRETAPIKEY`
  - Optional: `SUBDOMAINS`, `PUBLIC_IPS`, `FRITZBOX` (handled via `fritzbox-ips` sidecar subprocess), `IPV4`, `IPV6`, `SLEEP`, `DEBUG`, `LOG_LEVEL`, `RETRY_COUNT`, `RETRY_DELAY`, `WEBHOOK_URL`, `WEBHOOK_TEMPLATE`, `WEBHOOK_TEMPLATE_FILE`, `API_ENDPOINT`
- **Multi-arch builds:** Platform list in `.github/platforms.json`, not hardcoded in workflows
- **Secrets:** GitHub App token (APP_ID + APP_PRIVATE_KEY) for CI automation, Docker Hub credentials for image publishing, PyPI trusted publisher (no token needed)

## Agent skills

### Issue tracker

Issues live as GitHub issues; use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical triage roles map to labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wont-fix` (wontfix role). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
