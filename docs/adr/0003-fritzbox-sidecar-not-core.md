# 0003 — Fritzbox IP Discovery as a Sidecar, Not a Core Concern

- **Status:** accepted
- **Date:** 2026-08-03

## Context

Fritzbox UPnP IP discovery was a core concern of `PorkbunDDNS.get_public_ips`, untested, and dragged the `PublicIPResolver`'s surface. The path is niche, and discovering an IP from a UPnP router is upstream-of-IP-discovery, not IP-discovery itself. The v2.0.0 major release gives license to reshape the public surface.

## Decision

Extract fritzbox IP discovery to a sidecar console-script (`fritzbox-ips`) invoked by `Docker/entrypoint.py` to preserve the `FRITZBOX` env. Drop `fritzbox_ip` from the `PorkbunDDNS` constructor. Drop the fritzbox branch from `PublicIPResolver` (now two sources: static + public-HTTP).

## Considered Options

- **Reintroduce fritzbox as a swappable `IPSource` adapter in `PublicIPResolver`** — rejected: YAGNI; there is one fritzbox implementation and no real adapter variation.

## Consequences

- Docker `FRITZBOX` env unchanged.
- Pip users migrate `--fritzbox <ip>` to the `fritzbox-ips <ip>` console-script, piped into `--public-ips`.
- `PublicIPResolver` becomes two-source only.
- `PorkbunDDNS` constructor shrinks.
- `helpers.get_ips_from_fritzbox` stays in the package (called by the sidecar), not from core.