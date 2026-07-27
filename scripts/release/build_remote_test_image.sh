#!/usr/bin/env bash
set -euo pipefail

CONTEXT_DIR="${1:?usage: build_remote_test_image.sh CONTEXT_DIR CONTEXT_HASH}"
CONTEXT_HASH="${2:?usage: build_remote_test_image.sh CONTEXT_DIR CONTEXT_HASH}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.cloud.tencent.com/pypi/simple}"

if [[ ! "${CONTEXT_HASH}" =~ ^[a-f0-9]{64}$ ]]; then
  echo "invalid backend context hash" >&2
  exit 1
fi
if [[ ! -d "${CONTEXT_DIR}" || ! -f "${CONTEXT_DIR}/Dockerfile" ]]; then
  echo "invalid remote build context" >&2
  exit 1
fi
if [[ ! "${PIP_INDEX_URL}" =~ ^https:// ]]; then
  echo "PIP_INDEX_URL must use https" >&2
  exit 1
fi

IMAGE="yujian-test-local:ctx-${CONTEXT_HASH:0:24}"
if docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "reusing cached test image ${IMAGE}" >&2
else
  DOCKER_BUILDKIT=1 docker build \
    --file "${CONTEXT_DIR}/Dockerfile" \
    --build-arg "BUILD_CONTEXT_HASH=${CONTEXT_HASH}" \
    --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}" \
    --tag "${IMAGE}" \
    "${CONTEXT_DIR}"
  echo "built test image ${IMAGE}" >&2
fi

actual_hash="$(docker image inspect "${IMAGE}" --format '{{ index .Config.Labels "org.opencontainers.image.source-hash" }}')"
if [[ "${actual_hash}" != "${CONTEXT_HASH}" ]]; then
  echo "test image context hash mismatch" >&2
  exit 1
fi
printf '%s\n' "${IMAGE}"
