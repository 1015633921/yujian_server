#!/usr/bin/env bash
set -euo pipefail

docker exec -i yujian-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --batch --skip-column-names' <<'SQL'
SELECT 'production', 'users', COUNT(*) FROM yujian.users;
SELECT 'production', 'orders', COUNT(*) FROM yujian.orders;
SELECT 'production', 'materials', COUNT(*) FROM yujian.managed_materials;
SELECT 'test', 'users', COUNT(*) FROM yujian_test.users;
SELECT 'test', 'orders', COUNT(*) FROM yujian_test.orders;
SELECT 'test', 'materials', COUNT(*) FROM yujian_test.managed_materials;
SELECT 'local', 'users', COUNT(*) FROM yujian_local.users;
SELECT 'local', 'orders', COUNT(*) FROM yujian_local.orders;
SELECT 'local', 'materials', COUNT(*) FROM yujian_local.managed_materials;
INSERT INTO yujian_test.daily_checkins
  (user_id, checkin_date, mood, sleep, stress, created_at, updated_at)
VALUES
  ('dual-env-isolation-check', '2099-01-01', 5, 5, 1, '2099-01-01T00:00:00Z', '2099-01-01T00:00:00Z')
ON DUPLICATE KEY UPDATE updated_at=VALUES(updated_at);
SELECT 'test_isolation_row', COUNT(*) FROM yujian_test.daily_checkins
  WHERE user_id='dual-env-isolation-check';
SELECT 'production_isolation_row', COUNT(*) FROM yujian.daily_checkins
  WHERE user_id='dual-env-isolation-check';
INSERT INTO yujian_local.daily_checkins
  (user_id, checkin_date, mood, sleep, stress, created_at, updated_at)
VALUES
  ('local-env-isolation-check', '2099-01-02', 5, 5, 1, '2099-01-02T00:00:00Z', '2099-01-02T00:00:00Z')
ON DUPLICATE KEY UPDATE updated_at=VALUES(updated_at);
SELECT 'local_isolation_row', COUNT(*) FROM yujian_local.daily_checkins
  WHERE user_id='local-env-isolation-check';
SELECT 'production_local_isolation_row', COUNT(*) FROM yujian.daily_checkins
  WHERE user_id='local-env-isolation-check';
DELETE FROM yujian_test.daily_checkins WHERE user_id='dual-env-isolation-check';
DELETE FROM yujian_local.daily_checkins WHERE user_id='local-env-isolation-check';
DELETE FROM yujian_test.diy_designs WHERE order_id IN (
  SELECT order_id FROM yujian_test.orders WHERE user_id='test-env-smoke-user'
);
DELETE FROM yujian_test.orders WHERE user_id='test-env-smoke-user';
SQL
