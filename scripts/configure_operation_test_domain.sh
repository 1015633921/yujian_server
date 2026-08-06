#!/usr/bin/env bash
set -euo pipefail

DOMAIN="operation-test.yustream.cn"
CONFIG_DIR="/etc/nginx/conf.d"
CONFIG_PATH="${CONFIG_DIR}/yujian-operation-test.conf"
WEBROOT="/var/www/letsencrypt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HTTP_TEMPLATE="${ROOT_DIR}/deploy/nginx/yujian-operation-test-http.conf"
HTTPS_TEMPLATE="${ROOT_DIR}/deploy/nginx/yujian-operation-test.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "must run as root" >&2
  exit 1
fi
if [[ ! -f "${HTTP_TEMPLATE}" || ! -f "${HTTPS_TEMPLATE}" ]]; then
  echo "operation-test Nginx templates are missing" >&2
  exit 1
fi
if ! getent ahostsv4 "${DOMAIN}" >/dev/null; then
  echo "${DOMAIN} has no IPv4 DNS record" >&2
  exit 1
fi
if ! command -v certbot >/dev/null; then
  echo "certbot is required to provision ${DOMAIN}" >&2
  exit 1
fi

mkdir -p "${WEBROOT}" "${CONFIG_DIR}"
install -m 0644 "${HTTP_TEMPLATE}" "${CONFIG_PATH}"
nginx -t
nginx -s reload

certbot certonly --webroot --non-interactive --keep-until-expiring \
  --webroot-path "${WEBROOT}" --domains "${DOMAIN}"

install -m 0644 "${HTTPS_TEMPLATE}" "${CONFIG_PATH}"
nginx -t
nginx -s reload

curl --fail --silent --show-error --max-time 10 "https://${DOMAIN}/health/ready" >/dev/null
echo "operation test domain configured: https://${DOMAIN}/"
