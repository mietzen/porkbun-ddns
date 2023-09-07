#!/usr/bin/env bash

set -xe

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "Setup"
docker run -d --rm \
    --name porkbun-ddns \
    --platform ${PLATFORM} \
    --env "SLEEP=301" \
    --volume ${SCRIPT_DIR}/assets/:/tmp/test-assets \
    --entrypoint /tmp/test-assets/entrypoint.py \
    "${DOCKER_USER}/porkbun-ddns:${VERSION}-${ARCH}-${BUILD_NR}"

# Install tools needed for inspect
docker exec -u 0 porkbun-ddns apt-get update
docker exec -u 0 porkbun-ddns apt-get install procps -y

echo "Test"
inspec exec ./test/integration -t docker://porkbun-ddns
echo "Teardown"
docker container stop porkbun-ddns
