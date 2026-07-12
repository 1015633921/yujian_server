#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PORT="${APP_PORT:?set APP_PORT}"
APP_SLOT="${APP_SLOT:?set APP_SLOT}"
APP_IMAGE="${APP_IMAGE:?set APP_IMAGE}"
RELEASE_VERSION="${RELEASE_VERSION:?set RELEASE_VERSION}"
PROJECT="${PROJECT:?set candidate Compose project name}"
NGINX_UPSTREAM_FILE="${NGINX_UPSTREAM_FILE:?set NGINX_UPSTREAM_FILE}"
RELEASE_STATE_DIR="${RELEASE_STATE_DIR:-/opt/yujian/releases/state}"

python3 "${ROOT}/scripts/validate_image_ref.py" "${APP_IMAGE}"
curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/health/ready" >/dev/null
mkdir -p "${RELEASE_STATE_DIR}"
test -w "${RELEASE_STATE_DIR}"

temporary="$(mktemp "${NGINX_UPSTREAM_FILE}.XXXXXX")"
backup="$(mktemp "${NGINX_UPSTREAM_FILE}.backup.XXXXXX")"
trap 'rm -f "${temporary}" "${backup}"' EXIT
if [[ -f "${NGINX_UPSTREAM_FILE}" ]]; then
  cp "${NGINX_UPSTREAM_FILE}" "${backup}"
fi
printf 'upstream yujian_active {\n    server 127.0.0.1:%s;\n    keepalive 32;\n}\n' "${APP_PORT}" > "${temporary}"
mv "${temporary}" "${NGINX_UPSTREAM_FILE}"
if ! nginx -t || ! nginx -s reload; then
  if [[ -s "${backup}" ]]; then
    cp "${backup}" "${NGINX_UPSTREAM_FILE}"
    nginx -t && nginx -s reload
  fi
  echo "traffic switch failed; previous Nginx configuration restored" >&2
  exit 1
fi

python3 "${ROOT}/scripts/release_state.py" promote \
  --state-dir "${RELEASE_STATE_DIR}" \
  --release "${RELEASE_VERSION}" --slot "${APP_SLOT}" --port "${APP_PORT}" \
  --project "${PROJECT}" --image "${APP_IMAGE}"
echo "traffic switched to ${RELEASE_VERSION}; keep the previous release running during observation"
