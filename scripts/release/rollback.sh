#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NGINX_UPSTREAM_FILE="${NGINX_UPSTREAM_FILE:?set NGINX_UPSTREAM_FILE}"
RELEASE_STATE_DIR="${RELEASE_STATE_DIR:-/opt/yujian/releases/state}"

previous_port="$(python3 "${ROOT}/scripts/release_state.py" show --state-dir "${RELEASE_STATE_DIR}" --which previous --field port)"
previous_release="$(python3 "${ROOT}/scripts/release_state.py" show --state-dir "${RELEASE_STATE_DIR}" --which previous --field release)"
curl --fail --silent --show-error "http://127.0.0.1:${previous_port}/health/ready" >/dev/null

temporary="$(mktemp "${NGINX_UPSTREAM_FILE}.XXXXXX")"
backup="$(mktemp "${NGINX_UPSTREAM_FILE}.backup.XXXXXX")"
trap 'rm -f "${temporary}" "${backup}"' EXIT
cp "${NGINX_UPSTREAM_FILE}" "${backup}"
printf 'upstream yujian_active {\n    server 127.0.0.1:%s;\n    keepalive 32;\n}\n' "${previous_port}" > "${temporary}"
mv "${temporary}" "${NGINX_UPSTREAM_FILE}"
if ! nginx -t || ! nginx -s reload; then
  cp "${backup}" "${NGINX_UPSTREAM_FILE}"
  nginx -t && nginx -s reload
  echo "rollback switch failed; original Nginx configuration restored" >&2
  exit 1
fi
python3 "${ROOT}/scripts/release_state.py" rollback --state-dir "${RELEASE_STATE_DIR}"
echo "traffic rolled back to ${previous_release}; database was not downgraded"
