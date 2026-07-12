# P1 SKU 权威价格源整改结果

整改日期：2026-07-12
代码状态：**已修复，待 MySQL 门禁与候选 CI 验证**
项目整体状态：**NO-GO**

## 目标

订单金额不再从 `managed_materials.price` 浮点字段计算。新增 `managed_materials.price_cents` 整数分字段，作为 SKU 唯一交易权威价格源。

旧 `price` 字段继续双写，仅用于旧应用回滚和现有前端展示兼容，不参与订单金额、支付金额或商品快照计算。新建 MySQL 表的兼容字段使用 `DECIMAL(12,2)`；已有库不在本次 additive migration 中原地改列类型。

## 实现

- 新增统一金额工具，使用 `Decimal` 校验输入并转换为整数分。
- 后台单个保存、批量改价、默认材料种子及所有材料导入脚本均双写 `price` 和 `price_cents`。
- 超过两位小数、NaN、Infinity、负数和超范围价格在写入前拒绝。
- 下单锁定 SKU 时只查询 `price_cents`，不再查询或回退 `price`。
- `price_cents` 为空、非整数、非正数或超范围时 fail closed，订单和库存预占均不创建。
- 订单项继续保存整数分单价、小计和服务端价格版本。

## 迁移

版本：`20260712_06_p1_material_price_cents`

迁移为 additive：

1. 新增 nullable `managed_materials.price_cents BIGINT`。
2. 只回填大于 0、范围合法且乘 100 后可精确落到整数分的旧价格。
3. 零价格、超过两位小数或异常数据保持 `NULL`，由应用拒单并要求人工修正。
4. 不删除、不重命名旧 `price` 字段。

## 执行前备份

本次没有连接或修改任何 MySQL。对共享数据库执行迁移前，必须先运行项目备份脚本并单独备份材料表：

```sql
CREATE TABLE managed_materials_backup_20260712 LIKE managed_materials;
INSERT INTO managed_materials_backup_20260712 SELECT * FROM managed_materials;
SELECT COUNT(*) FROM managed_materials;
SELECT COUNT(*) FROM managed_materials_backup_20260712;
```

两表行数一致并记录备份 ID、校验和后，才允许运行：

```bash
python -m app.migrations.runner upgrade --backend mysql
```

## 升级后校验

```sql
SELECT COUNT(*) AS enabled_without_authoritative_price
FROM managed_materials
WHERE enabled = 1 AND (price_cents IS NULL OR price_cents <= 0);

SELECT COUNT(*) AS dual_write_mismatch
FROM managed_materials
WHERE price_cents IS NOT NULL
  AND ABS((price * 100) - price_cents) >= 0.000001;

SELECT id, skuId, name, price, price_cents
FROM managed_materials
WHERE price_cents IS NULL OR price_cents <= 0
ORDER BY updated_at DESC;
```

`enabled_without_authoritative_price` 和 `dual_write_mismatch` 必须为 0，才能考虑开启 checkout。异常 SKU 应在后台重新保存合法价格；不得手工猜测或静默回填。

## 回滚

首选应用回滚：切回旧应用并保留 additive `price_cents` 字段。因为新代码持续双写旧 `price`，旧应用仍可读取兼容价格。

只有在已确认旧应用稳定、备份可恢复且获得数据库变更审批后，才执行：

```bash
python -m app.migrations.runner downgrade --backend mysql --steps 1
```

该操作只删除 `price_cents`，不会删除旧 `price`。执行前仍需再次备份 `managed_materials`。

## 测试证据

- 价格源专项：4 passed。
- 迁移、P0-B/P1-A 交易定向回归：69 passed。
- API、订单、支付和价格源回归：113 passed。
- SQLite migration round trip：通过。
- 完整后端：222 passed，4 skipped，无测试失败。
- MySQL migration/concurrency：本机环境不可用，未执行，不能由 SQLite 替代。

## 当前判断

代码层已消除浮点 SKU 字段作为订单权威价格源，原有推荐算法回归也已在后续整改中关闭。正式关闭该 P1 仍需：

1. 备份共享数据库材料表。
2. 在隔离或明确授权的 MySQL 环境执行迁移升级、校验和回退演练。
3. CI 对包含本迁移的不可变候选 commit 全绿。

`COMMERCE_CHECKOUT_ENABLED` 与 `WECHAT_PAYMENT_ENABLED` 继续保持 false。
