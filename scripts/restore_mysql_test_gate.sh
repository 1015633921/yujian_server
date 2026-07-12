#!/usr/bin/env bash
set -euo pipefail

BACKUP_PATH="${1:-}"
CONTAINER="${MYSQL_CONTAINER:-yujian-mysql}"
API_TEST_CONTAINER="${API_TEST_CONTAINER:-yujian-api-test}"

if [[ -z "${BACKUP_PATH}" || "$(basename "${BACKUP_PATH}")" != yujian_test_gate_*.sql.gz ]]; then
  echo "Usage: $0 /path/to/yujian_test_gate_YYYYMMDD_HHMMSS.sql.gz" >&2
  exit 2
fi
if [[ ! -f "${BACKUP_PATH}" ]]; then
  echo "Backup not found: ${BACKUP_PATH}" >&2
  exit 3
fi
if [[ "$(docker inspect -f '{{.State.Running}}' "${API_TEST_CONTAINER}" 2>/dev/null || true)" == "true" ]]; then
  echo "Stop ${API_TEST_CONTAINER} before restoring yujian_test." >&2
  exit 4
fi

gzip -t "${BACKUP_PATH}"
gunzip -c "${BACKUP_PATH}" \
  | docker exec -i "${CONTAINER}" sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'

docker exec "${CONTAINER}" sh -c \
  'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --batch --skip-column-names -e "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '\''yujian_test'\''"' \
  | awk '$1 > 0 { ok=1 } END { exit ok ? 0 : 1 }'

echo "Restored and verified yujian_test from ${BACKUP_PATH}."
