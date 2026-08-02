#!/usr/bin/env bash

if [[ ${{ runner.debug }} == 1 ]]; then
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

# The real image, real entrypoint, API_ENDPOINT -> mock, IPs pinned.
docker run -d --rm --name ${APP_CONTAINER} \
    --platform ${PLATFORM} \
    --network ${NETWORK} \
    -e DOMAIN=example.com \
    -e APIKEY=${APIKEY} \
    -e SECRETAPIKEY=${SECRETAPIKEY} \
    -e API_ENDPOINT="http://${MOCK_CONTAINER}:8000/api/json/v3" \
    -e PUBLIC_IPS=${PINNED_IP} \
    -e IPV6=FALSE \
    -e SLEEP=301 \
    "${IMAGE}"

# Poll the mock until the container's update pass created the record.
RETRIEVE_URL="http://127.0.0.1:${MOCK_PORT}/api/json/v3/dns/retrieve/example.com"
RECORDS="0"
for _ in $(seq 1 60); do
    RECORDS=$(curl -s -X POST "${RETRIEVE_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"apikey\":\"${APIKEY}\",\"secretapikey\":\"${SECRETAPIKEY}\"}" \
        | jq -r '.records | length' 2>/dev/null || echo "0")
    if [[ "${RECORDS}" != "0" && -n "${RECORDS}" ]]; then
        break
    fi
    sleep 2
done
[[ "${RECORDS}" != "0" && -n "${RECORDS}" ]] || fail "container never created the A record (records=${RECORDS})"

CONTENT=$(curl -s -X POST "${RETRIEVE_URL}" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"${APIKEY}\",\"secretapikey\":\"${SECRETAPIKEY}\"}" \
    | jq -r '.records[0].content' 2>/dev/null)
[[ "${CONTENT}" == "${PINNED_IP}" ]] || fail "expected content ${PINNED_IP}, got ${CONTENT}"

docker logs ${APP_CONTAINER}
docker logs ${APP_CONTAINER} | grep -q "Creating A-Record for example.com" \
    || fail "container log missing 'Creating A-Record for example.com'"

echo "Docker e2e PASSED: ${IMAGE} updated the mock via API_ENDPOINT (content=${CONTENT})"
