# Context: porkbun-ddns

porkbun-ddns is an unofficial DDNS client for Porkbun. It runs as a pip
package or a Docker container, and sets/updates A (IPv4) and AAAA (IPv6)
DNS records, only updating when IPs change.

## Glossary

- **e2e test**: A hermetic test that runs the client's full request path
  (Config → PorkbunDDNS → HTTP → mock API) without touching the real Porkbun
  API or real DNS records.
  _Avoid_: integration test, smoke test

- **smoke test**: A manual live-API harness (`local_test.py`, gitignored)
  that exercises real DNS records on a real domain with real API keys.
  _Avoid_: e2e test

- **mock**: The hand-written fake of the Porkbun JSON API v3 used by e2e
  tests, covering only the DNS endpoints the client calls.

- **fault injection**: The mock's `fail_next` counter, which makes the next N
  requests return HTTP 500 so the client's retry logic can be tested
  end-to-end.

- **endpoint override**: Pointing the client at a non-default API base URL
  (CLI `--endpoint`, `PORKBUN_ENDPOINT`/`API_ENDPOINT` env vars, config-file
  `endpoint`) — used to run against a mirror, proxy, or the mock.

- **canary**: A scheduled check (GitHub Actions `api-canary.yml`) that
  verifies the default API endpoint is reachable and the mock still conforms
  to the live API spec.
