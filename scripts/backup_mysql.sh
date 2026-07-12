#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/yujian_server}"
BACKUP_DIR="${APP_DIR}/backups/mysql"
CONTAINER="${MYSQL_CONTAINER:-yujian-mysql}"
DATABASE="${BACKUP_DATABASE:?set the single database to back up}"
STAMP="$(date +%Y%m%d_%H%M%S)"

if [[ ! "${DATABASE}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "invalid BACKUP_DATABASE" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

TARGET="${BACKUP_DIR}/${DATABASE}_${STAMP}.sql.gz"
TEMP="${TARGET}.tmp"
docker exec "${CONTAINER}" sh -c \
  "exec mysqldump --single-transaction --quick --routines --events --triggers -uroot -p\"\$MYSQL_ROOT_PASSWORD\" ${DATABASE}" \
  | gzip -9 > "${TEMP}"

test -s "${TEMP}"
mv "${TEMP}" "${TARGET}"
sha256sum "${TARGET}" > "${TARGET}.sha256"
printf 'database=%s\nrelease=%s\noperator=%s\ncreated_at=%s\n' \
  "${DATABASE}" "${RELEASE_VERSION:-unversioned}" "${MIGRATION_OPERATOR:-unknown}" "$(date -Iseconds)" \
  > "${TARGET}.meta"

find "${BACKUP_DIR}" -type f -name '*.sql.gz' -mtime +15 -delete
find "${BACKUP_DIR}" -type f -name '*.sql.gz.sha256' -mtime +15 -delete
find "${BACKUP_DIR}" -type f -name '*.sql.gz.meta' -mtime +15 -delete

echo "backup created: ${TARGET}"
