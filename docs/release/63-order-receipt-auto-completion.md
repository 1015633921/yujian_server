# 订单签收与自动完成上线手册

## 状态规则

- 物流从运输中变为已签收时，订单仍保持 `shipped`。
- 用户确认收货后，订单立即转为 `completed`。
- 用户未确认时，独立物流 worker 在签收满 7 天后自动完成。
- 用户确认和自动任务共用订单行锁，重复执行不会追加第二条完成记录。
- 后台通用状态修改入口不允许直接将订单改为 `completed`。

## 迁移

版本：`20260713_07_order_receipt_completion`

新增：

- `orders.logistics_signed_at VARCHAR(40) NULL`
- `orders.auto_complete_at VARCHAR(40) NULL`
- `idx_orders_auto_complete(status, auto_complete_at)`

迁移会回填已经处于 `shipped` 且 `logistics_json.status=signed` 的历史订单。

## 上线顺序

1. 停止物流 worker，记录当前应用版本。
2. 对 `orders` 表和整库生成带 checksum 的备份，并在隔离副本验证可恢复。
3. 设置 `MIGRATION_OPERATOR` 和 `RELEASE_VERSION`，执行 `python -m app.migrations.runner upgrade --backend mysql`。
4. 确认 `schema_migrations` 已记录新版本，两个字段和索引存在。
5. 部署新 API 和小程序，再恢复独立物流 worker。
6. 使用非真实客户订单验证“运输中 -> 已签收 -> 待确认收货 -> 已完成”。

## 数据校验

```sql
SELECT status, COUNT(*)
FROM orders
GROUP BY status;

SELECT COUNT(*) AS invalid_signed_deadline
FROM orders
WHERE status = 'shipped'
  AND logistics_signed_at IS NOT NULL
  AND auto_complete_at IS NULL;

SELECT order_id, logistics_signed_at, auto_complete_at
FROM orders
WHERE status = 'shipped' AND auto_complete_at IS NOT NULL
ORDER BY auto_complete_at ASC
LIMIT 20;
```

`invalid_signed_deadline` 必须为 0。不得在生产环境为了测试人工把截止时间改到过去。

## 回滚

优先停止物流 worker 并回滚应用，保留新字段。只有在新应用和 worker 全部停止、已再次备份且确认无依赖后，才可执行：

```text
python -m app.migrations.runner downgrade --backend mysql --steps 1
```

数据库 downgrade 会删除两个时间字段及索引；若已有新版本签收数据，默认不执行 downgrade。
