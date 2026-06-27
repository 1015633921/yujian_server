#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/yujian_server"
BACKUP_DIR="${APP_DIR}/backups/mysql"
CONTAINER="yujian-mysql"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${BACKUP_DIR}"

for DATABASE in yujian yujian_test yujian_local; do
  TARGET="${BACKUP_DIR}/${DATABASE}_${STAMP}.sql.gz"
  TEMP="${TARGET}.tmp"
  docker exec "${CONTAINER}" sh -c \
    "exec mysqldump --single-transaction --quick --routines --events --triggers -uroot -p\"\$MYSQL_ROOT_PASSWORD\" ${DATABASE}" \
    | gzip -9 > "${TEMP}"

  test -s "${TEMP}"
  mv "${TEMP}" "${TARGET}"
done

find "${BACKUP_DIR}" -type f -name 'yujian*.sql.gz' -mtime +15 -delete
