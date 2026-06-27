#!/usr/bin/env bash
set -euo pipefail

SOURCE_DB="${1:-yujian_test}"
TARGET_DB="${2:-yujian_local}"
CONTAINER="${CONTAINER:-yujian-mysql}"

case "${SOURCE_DB}:${TARGET_DB}" in
  yujian_test:yujian_local|yujian:yujian_local)
    ;;
  *)
    echo "Refusing to clone ${SOURCE_DB} -> ${TARGET_DB}. Allowed targets: yujian_local only." >&2
    exit 2
    ;;
esac

docker exec "${CONTAINER}" sh -c "exec mysqldump --single-transaction --quick --routines --events --triggers -uroot -p\"\$MYSQL_ROOT_PASSWORD\" ${SOURCE_DB}" \
  | docker exec -i "${CONTAINER}" sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" ${TARGET_DB}"

echo "Cloned ${SOURCE_DB} -> ${TARGET_DB}"
