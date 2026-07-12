#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_SLOT="${APP_SLOT:?set APP_SLOT to blue or green}"
APP_PORT="${APP_PORT:?set the candidate localhost port}"
APP_IMAGE="${APP_IMAGE:?set APP_IMAGE to repository@sha256:digest}"
RELEASE_VERSION="${RELEASE_VERSION:?set RELEASE_VERSION}"
ENVIRONMENT="${ENVIRONMENT:?set ENVIRONMENT to test or prod}"
ENV_FILE="${ENV_FILE:?set ENV_FILE}"
CERTS_DIR="${CERTS_DIR:?set CERTS_DIR}"
BACKEND_NETWORK="${BACKEND_NETWORK:?set BACKEND_NETWORK}"
PROJECT="yujian-${APP_SLOT}-${RELEASE_VERSION}"

[[ "${APP_SLOT}" =~ ^(blue|green)$ ]] || { echo "invalid APP_SLOT" >&2; exit 1; }
python3 "${ROOT}/scripts/validate_image_ref.py" "${APP_IMAGE}"
python3 "${ROOT}/scripts/validate_release_env.py" --environment "${ENVIRONMENT}" --env-file "${ENV_FILE}"

export APP_SLOT APP_PORT APP_IMAGE RELEASE_VERSION ENV_FILE CERTS_DIR BACKEND_NETWORK
docker compose --project-name "${PROJECT}" --file "${ROOT}/compose.release.yaml" pull api
image_release="$(docker image inspect "${APP_IMAGE}" --format '{{ index .Config.Labels "org.opencontainers.image.version" }}')"
if [[ "${image_release}" != "${RELEASE_VERSION}" ]]; then
  echo "image label release ${image_release} does not match ${RELEASE_VERSION}" >&2
  exit 1
fi
docker compose --project-name "${PROJECT}" --file "${ROOT}/compose.release.yaml" up --detach --no-build api

for _ in $(seq 1 30); do
  if curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/health/ready" >/dev/null; then
    curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/health/live" >/dev/null
    echo "candidate ready: release=${RELEASE_VERSION} slot=${APP_SLOT} project=${PROJECT}"
    exit 0
  fi
  sleep 2
done

docker compose --project-name "${PROJECT}" --file "${ROOT}/compose.release.yaml" logs --tail 100 api >&2
echo "candidate readiness failed; active traffic was not changed" >&2
exit 1
