#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/yujian_server"
cd "${APP_DIR}"

set -a
source ./.env
set +a

docker exec -i yujian-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<SQL
CREATE DATABASE IF NOT EXISTS yujian CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS yujian_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS yujian_local CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON yujian.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON yujian_test.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON yujian_local.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL

{
  echo "APP_ENV=test"
  echo "DATABASE_BACKEND=mysql"
  grep -E '^(WECHAT_APP_ID|WECHAT_APP_SECRET|MYSQL_HOST|MYSQL_PORT|MYSQL_USER|MYSQL_PASSWORD)=' .env
  echo "MYSQL_DATABASE=yujian_test"
  echo "WECHAT_PAY_TEST_MODE=true"
  echo "LOGISTICS_SYNC_ENABLED=false"
} > .env.test

{
  echo "APP_ENV=local"
  echo "DATABASE_BACKEND=mysql"
  grep -E '^(WECHAT_APP_ID|WECHAT_APP_SECRET|MYSQL_HOST|MYSQL_PORT|MYSQL_USER|MYSQL_PASSWORD)=' .env
  echo "MYSQL_DATABASE=yujian_local"
  echo "WECHAT_PAY_TEST_MODE=true"
  echo "LOGISTICS_SYNC_ENABLED=false"
} > .env.local

chmod 600 .env.test
chmod 600 .env.local
docker compose config --quiet
