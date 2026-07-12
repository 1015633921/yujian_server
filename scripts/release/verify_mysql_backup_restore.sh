#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${BACKUP_FILE:?set BACKUP_FILE to a .sql.gz backup}"
RESTORE_DATABASE="${RESTORE_DATABASE:?set RESTORE_DATABASE to an isolated restore_test database}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:?set MYSQL_USER}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:?set MYSQL_PASSWORD}"

if [[ ! "${RESTORE_DATABASE}" =~ (restore|test|ci) ]]; then
  echo "RESTORE_DATABASE must contain restore, test or ci" >&2
  exit 1
fi
test -s "${BACKUP_FILE}"
test -s "${BACKUP_FILE}.sha256"
(cd "$(dirname "${BACKUP_FILE}")" && sha256sum --check "$(basename "${BACKUP_FILE}.sha256")")
gzip --test "${BACKUP_FILE}"

export MYSQL_PWD="${MYSQL_PASSWORD}"
mysql --host "${MYSQL_HOST}" --port "${MYSQL_PORT}" --user "${MYSQL_USER}" \
  --execute "DROP DATABASE IF EXISTS \`${RESTORE_DATABASE}\`; CREATE DATABASE \`${RESTORE_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gzip --decompress --stdout "${BACKUP_FILE}" | mysql --host "${MYSQL_HOST}" --port "${MYSQL_PORT}" --user "${MYSQL_USER}" "${RESTORE_DATABASE}"
table_count="$(mysql --batch --skip-column-names --host "${MYSQL_HOST}" --port "${MYSQL_PORT}" --user "${MYSQL_USER}" \
  --execute "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='${RESTORE_DATABASE}';")"
if [[ "${table_count}" -lt 1 ]]; then
  echo "backup restore produced no tables" >&2
  exit 1
fi
mysql --host "${MYSQL_HOST}" --port "${MYSQL_PORT}" --user "${MYSQL_USER}" --execute "DROP DATABASE \`${RESTORE_DATABASE}\`;"
echo "backup checksum and isolated restore verified"
