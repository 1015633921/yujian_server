# P0-B 订单完整性迁移手册

## 变更范围

迁移版本 `20260712_02_p0b_order_integrity` 依赖 P0-A 迁移，并以扩展方式增加：

- `orders.idempotency_key`、`orders.request_hash`、`orders.reservation_expires_at`。
- `managed_materials.reserved_stock`，默认 `0`。
- `order_requests`，主键为 `(user_id, idempotency_key)`。
- `inventory_reservations`，保存订单、SKU、数量、状态和过期时间。
- 订单用户与幂等键唯一索引、预占过期和 SKU 状态索引。

迁移不删除或改写现有订单。`orders.total_fee` 是订单金额的整数分权威字段；旧 `total_amount` 仅为兼容字段，不参与定价、库存或支付金额判断。

## 升级步骤

1. 确认 `COMMERCE_CHECKOUT_ENABLED=false`，停止新建订单流量。
2. 备份目标数据库并记录备份标识、代码版本和迁移前行数。
3. 确认目标是隔离测试库，先执行升级：

```bash
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner upgrade --backend mysql
```

SQLite 演练：

```bash
.venv_codex/bin/python -m app.migrations.runner upgrade --backend sqlite --sqlite-path /tmp/yujian-p0b.db
```

4. 重复执行一次 upgrade，结果必须为 `no changes`。
5. 确认 `schema_migrations` 包含 `20260712_02_p0b_order_integrity`。
6. 执行下方校验 SQL，全部异常计数必须为 `0`。
7. 在隔离 MySQL 8 测试库运行 50 并发测试和应用冒烟。P0-B 不授权开启结算或真实支付。

## 数据校验

```sql
SELECT COUNT(*) AS invalid_materials
FROM managed_materials
WHERE stock < 0 OR reserved_stock < 0 OR reserved_stock > stock;

SELECT COUNT(*) AS invalid_reservations
FROM inventory_reservations
WHERE quantity <= 0
   OR status NOT IN ('reserved', 'confirmed', 'released', 'expired');

SELECT COUNT(*) AS duplicate_requests
FROM (
  SELECT user_id, idempotency_key, COUNT(*) AS c
  FROM order_requests
  GROUP BY user_id, idempotency_key
  HAVING COUNT(*) > 1
) AS duplicates;

SELECT COUNT(*) AS reservation_mismatches
FROM managed_materials AS m
LEFT JOIN (
  SELECT sku_id, SUM(quantity) AS quantity
  FROM inventory_reservations
  WHERE status = 'reserved'
  GROUP BY sku_id
) AS r ON r.sku_id = m.id
WHERE m.reserved_stock <> COALESCE(r.quantity, 0);

SELECT COUNT(*) AS broken_order_requests
FROM order_requests AS r
LEFT JOIN orders AS o ON o.order_id = r.order_id
WHERE r.order_id IS NOT NULL AND o.order_id IS NULL;
```

## 过期预占任务

由单独的定时任务使用管理员 Bearer 调用：

```http
POST /api/v1/admin/maintenance/inventory-reservations/release-expired?limit=100
Authorization: Bearer <admin-token>
```

接口可以重复执行。它只处理 `status=reserved` 且已过期的记录；已释放、已过期或已确认记录不会重复修改库存。本阶段禁止在每个 Uvicorn worker 内启动过期扫描线程。

## 回滚

优先回退应用代码并继续保持 `COMMERCE_CHECKOUT_ENABLED=false`，数据库扩展字段和表可以保留。这是推荐方案。

只有同时满足以下条件才允许结构回滚：

- 所有新版本应用实例和过期任务均已停止。
- 没有 `status=reserved` 的预占记录。
- 已保存数据库备份，且确认不需要保留 P0-B 幂等与预占审计数据。

只回退最新 P0-B 迁移：

```bash
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner downgrade --backend mysql --steps 1
.venv_codex/bin/python -m app.migrations.runner downgrade --backend sqlite --sqlite-path /tmp/yujian-p0b.db --steps 1
```

回退会删除 P0-B 新增表、索引和字段，包括 `reserved_stock`，但保留 P0-A 会话和分享迁移。MySQL DDL 会自动提交，失败时应修复原因后重复执行幂等迁移，不能假设事务回滚了已完成的 DDL。
