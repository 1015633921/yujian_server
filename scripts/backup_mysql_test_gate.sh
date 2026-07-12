#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/yujian_server}"
DATABASE="${MYSQL_TEST_DATABASE:-yujian_test}"
CONTAINER="${MYSQL_CONTAINER:-yujian-mysql}"
API_TEST_CONTAINER="${API_TEST_CONTAINER:-yujian-api-test}"
BACKUP_DIR="${MYSQL_TEST_BACKUP_DIR:-${APP_DIR}/backups/mysql-gates}"
STAMP="$(date +%Y%m%d_%H%M%S)"

if [[ "${DATABASE}" != "yujian_test" ]]; then
  echo "Refusing to back up ${DATABASE}; this gate only permits yujian_test." >&2
  exit 2
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "${API_TEST_CONTAINER}" 2>/dev/null || true)" == "true" ]]; then
  echo "Stop ${API_TEST_CONTAINER} before taking the release-gate backup." >&2
  exit 3
fi

mkdir -p "${BACKUP_DIR}"
TARGET="${BACKUP_DIR}/${DATABASE}_gate_${STAMP}.sql.gz"
TEMP="${TARGET}.tmp"

docker exec "${CONTAINER}" sh -c \
  "exec mysqldump --single-transaction --quick --routines --events --triggers --add-drop-database --databases ${DATABASE} -uroot -p\"\$MYSQL_ROOT_PASSWORD\"" \
  | gzip -9 > "${TEMP}"

test -s "${TEMP}"
gzip -t "${TEMP}"
mv "${TEMP}" "${TARGET}"

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${TARGET}" > "${TARGET}.sha256"
else
  sha256sum "${TARGET}" > "${TARGET}.sha256"
fi

echo "MYSQL_TEST_BACKUP_ID=${TARGET}"
echo "Backup created and verified. Keep api-test stopped until the backup is restored."
