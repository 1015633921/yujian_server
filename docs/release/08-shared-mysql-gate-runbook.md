# 共享测试库 MySQL 门禁手册

P0-B、P1-A、P1-B 与 P1-C 的 MySQL 门禁统一使用长期测试库 `yujian_test`。禁止使用线上库 `yujian`。迁移门禁会执行数据库单步回退，必须在维护窗口内停止测试 API、备份整个测试库，并在门禁结束后恢复快照。

## 1. 停止写入并备份

在测试服务器执行：

```bash
cd /opt/yujian_server
docker compose stop api-test
./scripts/backup_mysql_test_gate.sh
```

记录脚本输出的完整 `MYSQL_TEST_BACKUP_ID`。备份包含 schema、索引、迁移版本和数据，并带 SHA-256 文件；只备份少量数据表不足以恢复 P1-A 的列与索引变化。

## 2. 建立本地隧道

从开发机建立到测试服务器 MySQL 的 SSH 隧道，例如本地端口 `3307`。门禁测试只允许通过 `127.0.0.1`、`localhost` 或容器主机 `mysql` 连接。

## 3. 运行 P0-B、P1-A、P1-B 与 P1-C

以下变量中的账号和密码必须来自 `.env.test`，不得使用线上独立凭据：

```bash
export ALLOW_SHARED_MYSQL_TEST_DATABASE=1
export MYSQL_TEST_BACKUP_ID=/opt/yujian_server/backups/mysql-gates/yujian_test_gate_YYYYMMDD_HHMMSS.sql.gz

RUN_P0B_MYSQL_INTEGRATION=1 \
P0B_MYSQL_TEST_HOST=127.0.0.1 \
P0B_MYSQL_TEST_PORT=3307 \
P0B_MYSQL_TEST_DATABASE=yujian_test \
P0B_MYSQL_TEST_USER=<test-user> \
P0B_MYSQL_TEST_PASSWORD=<test-password> \
.venv_codex/bin/python -m pytest -q tests/test_p0b_mysql_concurrency.py -m mysql_integration

RUN_P1A_MYSQL_INTEGRATION=1 \
P1A_MYSQL_TEST_HOST=127.0.0.1 \
P1A_MYSQL_TEST_PORT=3307 \
P1A_MYSQL_TEST_DATABASE=yujian_test \
P1A_MYSQL_TEST_USER=<test-user> \
P1A_MYSQL_TEST_PASSWORD=<test-password> \
.venv_codex/bin/python -m pytest -q tests/test_p1a_mysql_webhooks.py -m mysql_integration

RUN_P1B_MYSQL_INTEGRATION=1 \
P1B_MYSQL_TEST_HOST=127.0.0.1 \
P1B_MYSQL_TEST_PORT=3307 \
P1B_MYSQL_TEST_DATABASE=yujian_test \
P1B_MYSQL_TEST_USER=<test-user> \
P1B_MYSQL_TEST_PASSWORD=<test-password> \
.venv_codex/bin/python -m pytest -q tests/test_p1b_mysql_reports.py -m mysql_integration

RUN_P1C_MYSQL_INTEGRATION=1 \
P1C_MYSQL_TEST_HOST=127.0.0.1 \
P1C_MYSQL_TEST_PORT=3307 \
P1C_MYSQL_TEST_DATABASE=yujian_test \
P1C_MYSQL_TEST_USER=<test-user> \
P1C_MYSQL_TEST_PASSWORD=<test-password> \
.venv_codex/bin/python -m pytest -q tests/test_p1c_mysql_runtime.py -m mysql_integration

RUN_MATERIAL_MYSQL_INTEGRATION=1 \
MATERIAL_MYSQL_TEST_HOST=127.0.0.1 \
MATERIAL_MYSQL_TEST_PORT=3307 \
MATERIAL_MYSQL_TEST_DATABASE=yujian_test \
MATERIAL_MYSQL_TEST_USER=<test-user> \
MATERIAL_MYSQL_TEST_PASSWORD=<test-password> \
.venv_codex/bin/python -m pytest -q tests/test_material_mysql_concurrency.py -m mysql_integration
```

这条珠材门禁会并发提交同一 SKU 的同一修订号，并验证仅一条成功；随后用过期修订号执行批量库存操作，验证整批拒绝且库存不变化。

`ALLOW_SHARED_MYSQL_TEST_DATABASE` 和 `MYSQL_TEST_BACKUP_ID` 缺少任意一个时，测试必须拒绝使用 `yujian_test`。库名 `yujian` 永远不允许。

## 4. 恢复测试库

无论门禁成功或失败，都在测试 API 仍停止时恢复备份：

```bash
cd /opt/yujian_server
./scripts/restore_mysql_test_gate.sh \
  /opt/yujian_server/backups/mysql-gates/yujian_test_gate_YYYYMMDD_HHMMSS.sql.gz
docker compose up -d api-test
docker compose ps api-test
curl -fsS http://127.0.0.1:8001/health
```

恢复脚本只接受名称为 `yujian_test_gate_*.sql.gz` 的文件，使用 dump 中的 `DROP/CREATE DATABASE yujian_test` 完整恢复，并确认恢复后至少存在一张表。

## 5. 验收记录

记录备份 ID、Git HEAD、四个测试命令结果、恢复结果和测试 API 健康检查结果。不得把测试期间写入的订单、库存预占、支付事件、报告快照或运行任务记录保留在长期测试库中。
