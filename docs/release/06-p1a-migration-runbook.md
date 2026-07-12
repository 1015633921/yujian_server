# P1-A 支付事件迁移手册

## 迁移内容

版本 `20260712_03_p1a_payment_events` 依赖 P0-A 和 P0-B，只做扩展：

- 新增 `payment_webhook_events`，保存事件唯一键、类型、资源标识、报文 SHA-256、处理状态和脱敏失败分类。
- 为 `orders` 新增支付 provider、交易号、AppID、商户号、币种和确认时间字段。
- 新增 `(provider, provider_event_id)` 唯一索引、订单/状态/交易查询索引。
- 新增 `(payment_provider, payment_transaction_id)` 订单唯一索引。
- 不保存完整支付或退款回调原文，不删除旧字段，不改写旧支付 JSON。

## 升级

1. 确认以下开关保持关闭：

```text
COMMERCE_CHECKOUT_ENABLED=false
WECHAT_PAYMENT_ENABLED=false
```

2. 停止新实例放量，备份数据库并记录代码版本、备份标识和现有订单数。
3. 在升级前确认旧支付数据不存在交易号复用；查询必须返回 `0` 行：

```sql
SELECT order_id
FROM orders
WHERE payment_json IS NOT NULL AND payment_json <> '' AND JSON_VALID(payment_json) = 0;

SELECT JSON_UNQUOTE(JSON_EXTRACT(payment_json, '$.provider')) AS provider,
       JSON_UNQUOTE(JSON_EXTRACT(payment_json, '$.transaction_id')) AS transaction_id,
       COUNT(*) AS c
FROM orders
WHERE JSON_VALID(payment_json) = 1
  AND JSON_UNQUOTE(JSON_EXTRACT(payment_json, '$.transaction_id')) IS NOT NULL
  AND JSON_UNQUOTE(JSON_EXTRACT(payment_json, '$.transaction_id')) <> ''
GROUP BY provider, transaction_id
HAVING COUNT(*) > 1;
```

旧应用尚未写入结构化交易号；该预检用于在回填或启用新应用前发现历史冲突。P1-A 迁移本身不自动回填旧 `payment_json`。

4. 先在隔离测试库升级：

```bash
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner upgrade --backend mysql
```

SQLite 演练：

```bash
.venv_codex/bin/python - <<'PY'
from pathlib import Path
from app.admin_service import AdminService
from app.order_service import OrderService

path = Path('/tmp/yujian-p1a.db')
AdminService(path)
OrderService(path)
PY
.venv_codex/bin/python -m app.migrations.runner upgrade --backend sqlite --sqlite-path /tmp/yujian-p1a.db
```

版本化迁移以现有应用基线表为前置条件；不能对一个完全空白、未初始化旧 schema 的文件直接运行。

5. 重复执行 upgrade，结果必须为 `no changes`。
6. 确认 `schema_migrations` 包含 `20260712_03_p1a_payment_events`。
7. 执行数据校验并在开关关闭状态启动新应用。

## 数据校验

```sql
SELECT COUNT(*) AS duplicate_events
FROM (
  SELECT provider, provider_event_id, COUNT(*) AS c
  FROM payment_webhook_events
  GROUP BY provider, provider_event_id
  HAVING COUNT(*) > 1
) AS duplicates;

SELECT COUNT(*) AS invalid_event_status
FROM payment_webhook_events
WHERE processing_status NOT IN
  ('received', 'processing', 'failed', 'succeeded', 'ignored', 'compensation_required');

SELECT COUNT(*) AS transaction_reuse
FROM (
  SELECT payment_provider, payment_transaction_id, COUNT(*) AS c
  FROM orders
  WHERE payment_provider IS NOT NULL AND payment_transaction_id IS NOT NULL
  GROUP BY payment_provider, payment_transaction_id
  HAVING COUNT(*) > 1
) AS duplicates;

SELECT COUNT(*) AS paid_reservation_mismatch
FROM orders AS o
JOIN inventory_reservations AS r ON r.order_id = o.order_id
WHERE o.payment_status = 'paid' AND r.status <> 'confirmed';

SELECT COUNT(*) AS unpaid_confirmed_reservation
FROM orders AS o
JOIN inventory_reservations AS r ON r.order_id = o.order_id
WHERE o.payment_status IN ('unpaid', 'processing', 'failed', 'cancelled', 'expired')
  AND r.status = 'confirmed';
```

所有异常计数必须为 `0`。

## 失败与补偿

- `failed`：没有业务副作用或事务已整体回滚；微信使用相同已验签事件重试时可以再次处理。
- `ignored`：事件合法但订单已处于更高或不可逆状态，重复到达直接成功返回。
- `compensation_required`：已关闭/取消订单收到真实支付成功；不自动恢复订单或库存，需后台核对微信交易并按财务流程退款。
- `conflict_count > 0`：相同事件 ID 出现不同报文摘要，按安全事件调查，不处理第二份报文。

查询待人工处理事件：

```sql
SELECT provider_event_id, event_type, merchant_order_no, failure_reason, received_at
FROM payment_webhook_events
WHERE processing_status = 'compensation_required'
ORDER BY received_at;
```

台账不保存回调原文，因此服务端不会自行重放报文。正常失败依赖微信原事件重试；人工补偿使用受控的服务端查询抽象，不由用户页面直接调用微信。

## MySQL 验证

MySQL 门禁统一使用长期测试库 `yujian_test`。由于该测试会执行 P1-A 单步 downgrade/upgrade，运行前必须停止测试 API 并备份整个数据库，运行后无论成功或失败都必须恢复快照。完整命令见 `docs/release/08-shared-mysql-gate-runbook.md`。

测试验证并发投递同一支付事件时只产生一条事件、一条支付历史和一次库存确认。缺少 `ALLOW_SHARED_MYSQL_TEST_DATABASE=1` 或 `MYSQL_TEST_BACKUP_ID` 时，测试会拒绝使用 `yujian_test`；线上库 `yujian` 永远不允许。

## 回滚

推荐先回退应用并保持两个交易开关关闭；新增字段和表对旧应用是扩展结构，可以暂时保留。

只有确认没有新应用实例、没有正在处理的回调且已导出所有 `failed/compensation_required` 事件后，才单步回退：

```bash
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner downgrade --backend mysql --steps 1
.venv_codex/bin/python -m app.migrations.runner downgrade --backend sqlite --sqlite-path /tmp/yujian-p1a.db --steps 1
```

结构回退删除 P1-A 台账和订单支付结构化字段，但保留 P0-A/P0-B 表。MySQL DDL 会自动提交，失败后应修复并重复幂等步骤，不能假定已执行 DDL 自动回滚。
