# 0002 — Container-Level E2E via Sidecar Mock

- **Status:** accepted
- **Date:** 2026-08-02

## Context

The pytest e2e (ADR-0001) covers client logic against the in-process mock,
but the real Docker image, its entrypoint, and the `API_ENDPOINT` env-var
wiring (PR #146) were never exercised in CI — the existing inspec test mounts
a replacement entrypoint over `/entrypoint.py`.

## Decision

docker.yml runs a container-level e2e after inspec: the mock runs as a
sidecar `python:3.13-slim` container (native arch, no `--platform`) on a
shared docker network; the real image runs with `API_ENDPOINT` pointing at
the mock and `PUBLIC_IPS` pinned; `Docker/test/e2e.sh` asserts through the
mock's real `/dns/retrieve` endpoint and greps the container logs. Runs on
`linux/amd64` (ubuntu-latest) and `linux/arm64` (ubuntu-24.04-arm) only;
arm/v7 + v6 keep QEMU builds and inspec but skip the e2e. `platforms.json`
now carries a runner per platform.

## Considered Options

- **Host-side mock process** — rejected: relies on runner python setup + host
  networking.
- **e2e on all four arches** — rejected: QEMU arm/v6+v7 startup cost buys no
  extra signal — the wiring under test is arch-independent Python.
- **Mock control endpoint for assertions** — rejected: diverges from the real
  API surface.

## Consequences

- Real image + entrypoint + `API_ENDPOINT` wiring verified in CI on both
  native arch families.
- The e2e is network-isolated (docker-internal), distinct from the pytest
  e2e.
- arm/v6+v7 image correctness still covered by build + inspec.
