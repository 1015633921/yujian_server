# 交易系统最终审计

## 结论

服务端定价、订单幂等、库存预占、支付 Webhook 状态机的代码和定向测试基础较强，但存在生产模拟支付 P0，且 MySQL 并发与迁移门禁未执行。交易系统结论为 **FAIL / NO-GO**。checkout 与真实支付必须继续关闭。

## 检查结果

| 检查项 | 状态 | 证据 | 剩余风险 |
| --- | --- | --- | --- |
| 服务端权威定价 | PASS | 创建订单从服务端 SKU 读取并写不可变订单项快照；伪造 0 元/低价测试通过 | `managed_materials.price` 在 MySQL 仍为 `DOUBLE` |
| SKU fail closed | PASS | 不存在、下架、无价、非法价、查询异常、多 SKU 任一无效均有定向测试 | MySQL 实库异常路径未验证 |
| 订单金额 | PARTIAL | 订单项单价、小计和总额使用整数分，可从快照重算 | 权威 SKU 源字段为浮点，违反全链路 Decimal/整数分要求 |
| 幂等 | PASS | `current_user + Idempotency-Key`；同键同体返回原订单，同键异体 409；规范摘要有测试 | MySQL 唯一约束竞争未实跑 |
| 库存预占 | PASS | 创建订单与预占同事务；取消/超时释放、支付确认均幂等；定向测试通过 | MySQL 行锁和 50 并发门禁跳过 |
| 多 SKU 锁顺序 | PASS | 服务按稳定 SKU 顺序处理 | 只做静态和 SQLite 证据 |
| 支付 Webhook | PASS | 验签后去重；金额、币种、AppID、商户校验；乱序/重放状态机测试通过 | 真实微信证书与回调未调用 |
| 退款通知 | PASS | 状态一致性与重复通知安全有定向测试 | 真实退款未调用 |
| Feature Flag | PASS | `COMMERCE_CHECKOUT_ENABLED`、`WECHAT_PAYMENT_ENABLED` 缺失时均为 false；API 检查开关 | 模拟路由绕过这两个开关 |
| 模拟交易端点 | FAIL | `app/api.py:708`、`:718`；发布环境未强制关闭 `WECHAT_PAY_TEST_MODE` | 生产误配可绕过真实支付和履约 |

## MySQL 阻断项

本机没有 Docker、MySQL client，四组 MySQL gate 被 pytest 跳过。因此以下关键结论不能由 SQLite 替代：

- 50 个并发请求争抢有限库存；
- 多 SKU 并发与死锁行为；
- 幂等唯一键竞争；
- 订单、订单项、预占的事务回滚；
- Webhook 重放/乱序的行锁行为；
- 迁移升级、回退和备份恢复。

## 上线前要求

1. 关闭并隔离生产模拟支付/发货路由。
2. 将权威 SKU 价格迁移为整数分或明确精度的 `DECIMAL`，并验证双写/回滚策略。
3. 在隔离 MySQL 执行 P0-B/P1-A 全部门禁并保留日志。
4. checkout/payment 继续默认关闭，直到上述 P0/P1 关闭并完成真实支付沙箱验收。
