# 0001 — Focused Porkbun API Mock for E2E Tests

- **Status:** accepted
- **Date:** 2026-08-02

## Context

The client talks to the live Porkbun JSON API v3. We wanted hermetic
end-to-end coverage of all features (retry, webhooks, IPv4/IPv6) without
touching the real API or real DNS records.

## Decision

A focused hand-written stdlib mock covering only the 3 DNS endpoints the
client calls (retrieve, create, delete). Response shapes are sourced from the
official OpenAPI spec at https://porkbun.com/api/json/v3/spec, which is used
as a reference — not a code generator. Plain `jsonschema` validates mock
responses against the live spec in a network test that skips offline.

## Considered Options

- **Spec-driven full mock generated from the 167KB OpenAPI doc** — rejected:
  heavy new CI dependencies for ~57 endpoints the client never touches.
- **Live-API-only tests** — rejected: non-hermetic, requires real API keys.

## Consequences

- CI gains permanent regression coverage of retry, webhook, IPv4 and IPv6
  behavior.
- Spec drift or a default-endpoint outage surfaces as a CI or canary failure,
  prompting a mock or config update.
- The `nullable` keyword is ignored by jsonschema — the mock never returns
  nulls, so validation passes.
