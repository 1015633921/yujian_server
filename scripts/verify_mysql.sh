#!/usr/bin/env bash
set -euo pipefail

docker exec yujian-mysql sh -c '
  mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" <<SQL
CREATE TABLE IF NOT EXISTS deployment_health (
  id INT PRIMARY KEY,
  checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO deployment_health (id)
VALUES (1)
ON DUPLICATE KEY UPDATE checked_at = CURRENT_TIMESTAMP;
SELECT COUNT(*) AS rows_ok FROM deployment_health;
DROP TABLE deployment_health;
SQL
'
