#!/usr/bin/env bash

APT_SILENT='-qq -o=Dpkg::Use-Pty=0'

if [[ $CI_DEBUG_MODE == 1 ]]; then
    set -x
    APT_SILENT=''
fi

set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo ""
echo "--------------------------------------"
echo "Docker inspec"
echo "--------------------------------------"
echo ""

echo "Setup"
docker run -d --rm \
    --name porkbun-ddns \
    --platform ${PLATFORM} \
    --env "SLEEP=301" \
    --volume ${SCRIPT_DIR}/integration/assets/entrypoint.py:/entrypoint.py \
    "${DOCKER_USER}/porkbun-ddns:${VERSION}-${ARCH}-${BUILD_NR}"

# Install tools needed for inspect
docker exec -u 0 porkbun-ddns apt-get update 
docker exec -u 0 porkbun-ddns apt-get install procps -y $APT_SILENT

echo "Test"
inspec exec ./test/integration -t docker://porkbun-ddns
echo "Teardown"
docker container stop porkbun-ddns

echo ""
echo "--------------------------------------"
echo "Docker e2e"
echo "--------------------------------------"
echo ""

bash "${SCRIPT_DIR}/e2e.sh"
