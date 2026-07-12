# P0-B 验证记录

验证日期：2026-07-12。P0-B 代码与本地自动化进入验收阶段；项目整体仍为 **NO-GO**。

## 事务与幂等设计

- 创建订单要求 `Idempotency-Key`，数据库按 `(user_id, idempotency_key)` 唯一。
- 请求体使用稳定 JSON 计算 SHA-256。相同键和相同请求返回原订单；相同键不同请求返回 HTTP 409。
- 小程序每次主动结算生成新键；仅网络超时重试一次并复用原键。
- SKU 查询、服务端价格快照、订单写入和库存预占在同一事务中。MySQL 按 SKU ID 固定顺序执行 `SELECT ... FOR UPDATE`；SQLite 测试使用 `BEGIN IMMEDIATE`。
- 库存预占通过条件更新保证 `stock - reserved_stock >= quantity`。支付确认同时扣减 `stock` 和 `reserved_stock`；取消、失败或超时只释放 `reserved_stock`。
- 确认和释放按预占状态转换，重复调用不重复扣减。后台库存下调和 SKU 删除也使用带 `reserved_stock` 条件的原子 SQL。

## 定价与快照

- 客户端 `design`、`bom` 和明细价格不参与金额计算。
- SKU 不存在、下架、无价格、非法价格、查询异常或任一明细无效时，整个订单回滚。
- 金额计算使用 `Decimal` 转整数分；订单权威金额为 `total_fee`。
- 每行不可变快照包含 SKU ID/编码、名称、服务端单价分、数量、小计分及 `updated_at` 价格版本。
- 客户端展示价与服务端价不一致时返回 HTTP 409，小程序显示“价格已更新，请确认”并阻止支付。

## 自动化状态

已覆盖伪造 `0.01`/`0` 元、无效/混合 SKU、查询异常、非法数量、超库存、幂等重放与冲突、网络超时重试、取消/超时/重复释放、重复支付确认、事务回滚、SQLite 并发和后台库存保护。

| 命令 | 实际结果 |
|---|---|
| `pytest -q tests/test_p0b_order_integrity.py tests/test_p0b_migrations.py -p no:cacheprovider` | `18 passed, 1 warning` |
| `pytest -q --ignore=tests/minium -p no:cacheprovider` | `127 passed, 1 skipped, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `38 passed, 0 failed` |
| 全部 `miniprogram/**/*.js` 执行 `node --check` | 通过 |
| `python -m compileall -q app tests` | 通过 |
| SQLite upgrade、重复 upgrade、单步 downgrade、再次 upgrade | 成功、`no changes`、只回退 P0-B、再次成功 |
| `git diff --check` | 通过 |

全量测试的唯一失败是 P0-A 前已记录的推荐算法用例：财富愿望期望黄水晶等主石，实际返回 `green_phantom`。该用例不属于 P0-B，且本阶段禁止修改测算算法。`1 skipped` 是下述 MySQL 并发测试。

MySQL 50 并发用例位于 `tests/test_p0b_mysql_concurrency.py`。验收统一使用长期测试库 `yujian_test`，但必须先停止测试 API、完成整库可恢复备份，并提供共享库授权和备份 ID。完整命令与恢复步骤见 `docs/release/08-shared-mysql-gate-runbook.md`。

本机没有 Docker/MySQL 运行时，因此该用例当前**未执行**，不能以 SQLite 结果替代。正式验收前必须通过 SSH 隧道在已备份的 `yujian_test` 上跑通，并在结束后恢复快照。

## 发布判断

`COMMERCE_CHECKOUT_ENABLED` 在代码、Compose 和示例环境中继续默认 `false`。本阶段没有连接生产数据库、没有部署、没有启用真实结算或真实支付。P0-B 不改变项目整体结论：**NO-GO**。
