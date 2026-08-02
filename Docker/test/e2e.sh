#!/usr/bin/env bash

if [[ $CI_DEBUG_MODE == 1 ]]; then
    set -x
fi

set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
REPO_ROOT=$( cd "${SCRIPT_DIR}/../.." &> /dev/null && pwd )

# The e2e runs on the two native-runner platforms; arm/v6+v7 skip it.
if [[ "${PLATFORM}" != "linux/amd64" && "${PLATFORM}" != "linux/arm64" ]]; then
    echo "Skipping Docker e2e on ${PLATFORM} (native-runner platforms only)"
    exit 0
fi

NETWORK=porkbun-ddns-e2e
MOCK_CONTAINER=porkbun-ddns-mock
APP_CONTAINER=porkbun-ddns-e2e
MOCK_PORT=18080
IMAGE="${DOCKER_USER}/porkbun-ddns:${VERSION}-${ARCH}-${BUILD_NR}"
APIKEY=test-apikey
SECRETAPIKEY=test-secret
PINNED_IP=203.0.113.5
# ipaddress.IPv6Address("2001:db8::1").exploded - the client stores AAAA content exploded.
PINNED_IPV6=2001:0db8:0000:0000:0000:0000:0000:0001
STALE_IP=198.51.100.7

cleanup() {
    docker container stop ${APP_CONTAINER} >/dev/null 2>&1 || true
    docker container stop ${MOCK_CONTAINER} >/dev/null 2>&1 || true
    docker network rm ${NETWORK} >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

stop_app() {
    docker container stop ${APP_CONTAINER} >/dev/null 2>&1 || true
    docker rm -f ${APP_CONTAINER} >/dev/null 2>&1 || true
}

# POST to the mock's JSON API. $1 = path, e.g. /api/json/v3/dns/retrieve/example.com
mock_api() {
    curl -s -X POST "http://127.0.0.1:${MOCK_PORT}$1" \
        -H "Content-Type: application/json" \
        -d "{\"apikey\":\"${APIKEY}\",\"secretapikey\":\"${SECRETAPIKEY}\"}"
}

# Run the real image against the mock. $1 = DOMAIN, remaining args pass to docker run.
run_app() {
    stop_app
    docker run -d --rm --name ${APP_CONTAINER} \
        --platform ${PLATFORM} \
        --network ${NETWORK} \
        -e DOMAIN="$1" \
        -e APIKEY=${APIKEY} \
        -e SECRETAPIKEY=${SECRETAPIKEY} \
        -e API_ENDPOINT="http://${MOCK_CONTAINER}:8000/api/json/v3" \
        "${@:2}"
}

echo "Docker e2e - setup: starting mock sidecar"
docker network create ${NETWORK}

# Sidecar mock: native-arch python, runs the repo's mock standalone.
docker run -d --rm --name ${MOCK_CONTAINER} \
    --network ${NETWORK} \
    -p 127.0.0.1:${MOCK_PORT}:8000 \
    -e APIKEY=${APIKEY} \
    -e SECRETAPIKEY=${SECRETAPIKEY} \
    -e HOST=0.0.0.0 \
    -e PORT=8000 \
    -v "${REPO_ROOT}/porkbun_ddns/test/mock_porkbun_api.py":/mock.py \
    python:3.13-slim \
    python /mock.py

# Wait until the mock answers (any HTTP response proves the server is up).
for _ in $(seq 1 15); do
    if curl -s -o /dev/null "http://127.0.0.1:${MOCK_PORT}/api/json/v3/dns/retrieve/example.com"; then
        break
    fi
    sleep 2
done

echo "Docker e2e - scenario 1: IP change deletes + recreates, then stays idempotent"

# Seed a stale A record so the container must change it.
RESP=$(curl -s -X POST "http://127.0.0.1:${MOCK_PORT}/api/json/v3/dns/create/example.com" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"${APIKEY}\",\"secretapikey\":\"${SECRETAPIKEY}\",\"name\":\"@\",\"type\":\"A\",\"content\":\"${STALE_IP}\",\"ttl\":600}")
echo "${RESP}" | jq -e '.status == "SUCCESS"' >/dev/null \
    || fail "scenario 1: could not seed stale record: ${RESP}"

# SLEEP=1 so the loop runs a second (idempotent) pass while we watch.
run_app example.com -e PUBLIC_IPS=${PINNED_IP} -e IPV6=FALSE -e SLEEP=1 "${IMAGE}"

FLIPPED=""
for _ in $(seq 1 60); do
    FLIPPED=$(mock_api /api/json/v3/dns/retrieve/example.com \
        | jq -r '.records[] | select(.type == "A") | .content' 2>/dev/null | head -1 || true)
    [[ "${FLIPPED}" == "${PINNED_IP}" ]] && break
    sleep 2
done
[[ "${FLIPPED}" == "${PINNED_IP}" ]] \
    || fail "scenario 1: A record was not updated from ${STALE_IP} to ${PINNED_IP} (got: ${FLIPPED})"

# Wait for a second loop pass so idempotency is observable in the log.
SLEEPS=0
for _ in $(seq 1 30); do
    SLEEPS=$(docker logs ${APP_CONTAINER} 2>&1 | grep -c "Sleeping..." || true)
    [[ ${SLEEPS} -ge 2 ]] && break
    sleep 2
done
[[ ${SLEEPS} -ge 2 ]] || fail "scenario 1: container never completed a second loop pass"

LOG1=$(docker logs ${APP_CONTAINER} 2>&1)
CREATES=$(grep -c "Creating A-Record for example.com" <<< "${LOG1}" || true)
DELETES=$(grep -c "Deleting A-Record for example.com" <<< "${LOG1}" || true)
[[ ${CREATES} -eq 1 ]] || fail "scenario 1: expected exactly 1 create, got ${CREATES} (idempotency broken)"
[[ ${DELETES} -eq 1 ]] || fail "scenario 1: expected exactly 1 delete, got ${DELETES} (idempotency broken)"
grep -q "A-Record of example.com is up to date!" <<< "${LOG1}" \
    || fail "scenario 1: missing 'is up to date!' on unchanged pass"

echo "Docker e2e - scenario 2: IPv6 creates AAAA record"

run_app example.com -e PUBLIC_IPS=2001:db8::1 -e IPV4=FALSE -e IPV6=TRUE -e SLEEP=301 "${IMAGE}"

AAAA=""
for _ in $(seq 1 60); do
    AAAA=$(mock_api /api/json/v3/dns/retrieve/example.com \
        | jq -r '.records[] | select(.type == "AAAA") | .content' 2>/dev/null | head -1 || true)
    [[ "${AAAA}" == "${PINNED_IPV6}" ]] && break
    sleep 2
done
[[ "${AAAA}" == "${PINNED_IPV6}" ]] \
    || fail "scenario 2: AAAA record missing or wrong (got: ${AAAA})"

LOG2=$(docker logs ${APP_CONTAINER} 2>&1)
grep -q "Creating AAAA-Record for example.com" <<< "${LOG2}" \
    || fail "scenario 2: log missing 'Creating AAAA-Record for example.com'"

echo "Docker e2e - scenario 3: invalid configurations exit non-zero with a message"

LOG_DIR=$(mktemp -d)

# Missing required APIKEY
if docker run --rm \
    -e DOMAIN=example.com -e SECRETAPIKEY=${SECRETAPIKEY} \
    "${IMAGE}" > "${LOG_DIR}/missing-key.log" 2>&1; then
    fail "scenario 3: container without APIKEY should exit non-zero"
fi
grep -q "Please set DOMAIN, SECRETAPIKEY and APIKEY" "${LOG_DIR}/missing-key.log" \
    || fail "scenario 3: missing-APIKEY message not found"

# Both protocols disabled
if docker run --rm \
    -e DOMAIN=example.com -e APIKEY=${APIKEY} -e SECRETAPIKEY=${SECRETAPIKEY} \
    -e IPV4=FALSE -e IPV6=FALSE \
    "${IMAGE}" > "${LOG_DIR}/no-protocol.log" 2>&1; then
    fail "scenario 3: container with IPV4=FALSE IPV6=FALSE should exit non-zero"
fi
grep -q "No Protocol selected" "${LOG_DIR}/no-protocol.log" \
    || fail "scenario 3: no-protocol message not found"

# Deprecated IPV4_ONLY/IPV6_ONLY env vars
if docker run --rm \
    -e DOMAIN=example.com -e APIKEY=${APIKEY} -e SECRETAPIKEY=${SECRETAPIKEY} \
    -e IPV4_ONLY=TRUE \
    "${IMAGE}" > "${LOG_DIR}/deprecated.log" 2>&1; then
    fail "scenario 3: container with IPV4_ONLY should exit non-zero"
fi
grep -q "DEPRECATED" "${LOG_DIR}/deprecated.log" \
    || fail "scenario 3: deprecation message not found"

echo "Docker e2e - scenario 4: SUBDOMAINS creates records for each subdomain"

run_app example.org -e SUBDOMAINS="www,@" -e PUBLIC_IPS=${PINNED_IP} -e IPV6=FALSE -e SLEEP=301 "${IMAGE}"

COUNT=0
for _ in $(seq 1 60); do
    COUNT=$(mock_api /api/json/v3/dns/retrieve/example.org \
        | jq -r '.records | length' 2>/dev/null || echo 0)
    [[ ${COUNT} -ge 2 ]] && break
    sleep 2
done
[[ ${COUNT} -ge 2 ]] || fail "scenario 4: expected 2 records for SUBDOMAINS='www,@', got ${COUNT}"

NAMES=$(mock_api /api/json/v3/dns/retrieve/example.org \
    | jq -r '.records[].name' | sort | tr '\n' ' ')
[[ "${NAMES}" == "example.org www.example.org " ]] \
    || fail "scenario 4: unexpected record names: ${NAMES}"

LOG4=$(docker logs ${APP_CONTAINER} 2>&1)
grep -q "Creating A-Record for example.org" <<< "${LOG4}" \
    || fail "scenario 4: log missing 'Creating A-Record for example.org'"
grep -q "Creating A-Record for www.example.org" <<< "${LOG4}" \
    || fail "scenario 4: log missing 'Creating A-Record for www.example.org'"

echo "Docker e2e - scenario 5: DEBUG and LOG_LEVEL control log verbosity"

run_app example.net -e PUBLIC_IPS=${PINNED_IP} -e IPV6=FALSE -e SLEEP=301 -e DEBUG=TRUE "${IMAGE}"

for _ in $(seq 1 60); do
    COUNT=$(mock_api /api/json/v3/dns/retrieve/example.net \
        | jq -r '.records | length' 2>/dev/null || echo 0)
    [[ ${COUNT} -ge 1 ]] && break
    sleep 2
done
[[ ${COUNT} -ge 1 ]] || fail "scenario 5: DEBUG run created no record"
LOG5A=$(docker logs ${APP_CONTAINER} 2>&1)
grep -q "DEBUG" <<< "${LOG5A}" \
    || fail "scenario 5: no DEBUG-level log lines with DEBUG=TRUE"

run_app example.info -e PUBLIC_IPS=${PINNED_IP} -e IPV6=FALSE -e SLEEP=301 -e LOG_LEVEL=WARNING "${IMAGE}"

for _ in $(seq 1 60); do
    COUNT=$(mock_api /api/json/v3/dns/retrieve/example.info \
        | jq -r '.records | length' 2>/dev/null || echo 0)
    [[ ${COUNT} -ge 1 ]] && break
    sleep 2
done
[[ ${COUNT} -ge 1 ]] || fail "scenario 5: WARNING run created no record"
LOG5B=$(docker logs ${APP_CONTAINER} 2>&1)
if grep -qE "INFO|DEBUG" <<< "${LOG5B}"; then
    fail "scenario 5: INFO/DEBUG lines present with LOG_LEVEL=WARNING"
fi

echo "Docker e2e - scenario 6: RETRY_COUNT and RETRY_DELAY drive the retry loop"

stop_app

# Point at a closed port on the mock so every attempt fails fast with a
# connection error; the container must retry RETRY_COUNT times, sleeping
# RETRY_DELAY seconds between attempts, then exit non-zero.
START=$(date +%s)
if docker run --rm --name ${APP_CONTAINER} \
    --platform ${PLATFORM} \
    --network ${NETWORK} \
    -e DOMAIN=example.com \
    -e APIKEY=${APIKEY} \
    -e SECRETAPIKEY=${SECRETAPIKEY} \
    -e API_ENDPOINT="http://${MOCK_CONTAINER}:8001/api/json/v3" \
    -e PUBLIC_IPS=${PINNED_IP} \
    -e IPV6=FALSE \
    -e RETRY_COUNT=3 \
    -e RETRY_DELAY=1 \
    "${IMAGE}" > "${LOG_DIR}/retry.log" 2>&1; then
    fail "scenario 6: container should exit non-zero after exhausting retries"
fi
END=$(date +%s)

grep -q "attempt 1/3" "${LOG_DIR}/retry.log" \
    || fail "scenario 6: missing 'attempt 1/3' retry log line"
grep -q "attempt 2/3" "${LOG_DIR}/retry.log" \
    || fail "scenario 6: missing 'attempt 2/3' retry log line"
grep -q "Error reaching" "${LOG_DIR}/retry.log" \
    || fail "scenario 6: missing connection error in log"

ELAPSED=$((END - START))
[[ ${ELAPSED} -ge 2 ]] \
    || fail "scenario 6: expected >=2s wall time for RETRY_DELAY=1 x 2 sleeps, got ${ELAPSED}s"

echo "Docker e2e PASSED: ${IMAGE} (ip-change, ipv6, validation, subdomains, log-levels, retry)"
