# P1-A 支付完整性验证记录

验证日期：2026-07-12。当前结论：**P1-A BLOCKED，项目整体 NO-GO**。

P1-A 的 SQLite/本地实现与自动化已通过，但完成条件要求 MySQL 迁移和双 worker 并发去重必须真实通过。本机没有本地 MySQL 服务，`127.0.0.1:3306` 拒绝连接，不能用 SQLite 结果替代。后续统一通过 SSH 隧道使用已备份的长期测试库 `yujian_test`。

## 实现范围

- 支付与退款通知在验签后写入统一 `payment_webhook_events` 台账，按 `(provider, provider_event_id)` 数据库唯一去重。
- 相同事件和相同摘要幂等返回；相同事件 ID、不同摘要拒绝处理并记录安全冲突计数，不保存完整回调原文。
- 事件、订单、订单历史和库存预占确认/释放在同一事务中处理；失败整体回滚，事件可重试。
- 严格校验事件类型、AppID、商户号、订单号、交易号、币种和整数分金额；非法类型、浮点金额和超长事件 ID 均 fail closed。
- 已支付/已退款状态不被旧事件降级；关闭订单收到支付成功进入 `compensation_required`，不自动恢复订单或库存。
- 小程序只把 `wx.requestPayment.success` 视为客户端流程返回，随后有限退避轮询受鉴权的服务端状态；只有服务端返回已支付才显示支付成功。
- `COMMERCE_CHECKOUT_ENABLED` 与 `WECHAT_PAYMENT_ENABLED` 在缺少环境变量时均为 `false`。

完整转换规则见 `docs/release/05-payment-state-machine.md`，迁移与补偿步骤见 `docs/release/06-p1a-migration-runbook.md`。

## 验收结果

| 检查项 | 结果 | 证据 | 剩余风险 |
|---|---|---|---|
| 数据库级事件去重 | PASS（SQLite）/ BLOCKED（MySQL） | P1-A 定向测试 `31 passed`；MySQL 用例因 3306 拒绝连接失败 | 必须在已备份的 `yujian_test` 验证唯一键和行锁并发 |
| 支付通知严格校验 | PASS | AppID、商户号、订单、交易号、币种、整数分金额、事件类型和解密失败均有 fail-closed 用例 | 真实微信证书轮换和官方回调仍需测试环境联调 |
| 支付状态机与乱序 | PASS（本地） | 已支付不降级、关闭订单补偿、处理中转成功、终态失败释放库存均通过 | 补偿队列目前为人工查询，不是自动对账任务 |
| 事务与库存一致性 | PASS（SQLite）/ BLOCKED（MySQL） | 注入事务失败后订单、库存和事件回滚并可重试 | MySQL 实际事务隔离和双 worker 仍未验收 |
| 退款事件最小加固 | PASS | 去重、乱序、商户/交易号/金额/状态校验通过 | 不等于完整售后或自动对账系统 |
| 前端服务端确认 | PASS | JS `43 passed`；确认中、有限轮询、取消/未知状态、卸载停止和账号切换均覆盖 | 微信开发者工具和真机仍需人工走查 |
| P0-A/P0-B 回归 | PASS（本地） | 定向回归 `35 passed` | P0-B MySQL 50 并发门禁仍是既有阻塞 |
| SQLite 迁移往返 | PASS | upgrade、重复 upgrade、单步 downgrade、再次 upgrade 全部成功 | 迁移要求先存在旧版本应用基线 schema |
| Feature Flag | PASS | 缺少环境变量时 checkout/payment 均打印 `False` | 放量前仍需配置审查和双人确认 |
| 敏感日志/持久化扫描 | PASS（静态） | 未发现支付日志记录 body/payload/openid/Authorization；台账只保存 SHA-256 和脱敏分类 | 运行环境日志采集规则仍需部署侧确认 |

## 执行命令与真实结果

| 命令 | 结果 |
|---|---|
| `.venv_codex/bin/python -m pytest -q tests/test_p1a_payment_webhooks.py tests/test_p1a_migrations.py` | `31 passed, 1 warning` |
| `.venv_codex/bin/python -m pytest -q tests/test_p0a_security.py tests/test_p0a_migrations.py tests/test_p0b_order_integrity.py tests/test_p0b_migrations.py` | `35 passed, 1 warning` |
| `.venv_codex/bin/python -m pytest -q --ignore=tests/minium` | `158 passed, 2 skipped, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `43 passed, 0 failed` |
| 全部 `miniprogram/**/*.js` 执行 `node --check` | 通过，共 40 个文件 |
| `.venv_codex/bin/python -m compileall -q app tests` | 通过 |
| SQLite upgrade / 重复 upgrade / 单步 downgrade / upgrade | P0-A、P0-B、P1-A 成功 / `no changes` / 只回退 P1-A / P1-A 再次成功 |
| 缺省 Feature Flag 探针 | `checkout_enabled=False`、`payment_enabled=False` |
| `git diff --check` | 通过 |
| P1-A MySQL 迁移与并发用例 | **失败：** `pymysql.err.OperationalError (2003)`，`127.0.0.1:3306 Connection refused` |

全量测试的两个 skipped 分别是 P0-B 和 P1-A MySQL 集成测试；默认测试不得把它们当作已通过。

## 失败分类

原有失败：`tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements` 期望财富类主石，实际返回 `green_phantom`。该失败在 P1-A 基线前已存在，且本阶段禁止修改测算算法。

新增代码失败：本地可执行测试中没有新增失败。

验收阻塞：P1-A MySQL 测试无法连接隔离数据库。按完成条件，这使 P1-A 不能标记完成，也不能提交 P1-A 检查点。

## MySQL 解阻步骤

1. 按 `docs/release/08-shared-mysql-gate-runbook.md` 停止测试 API，并为 `yujian_test` 创建完整可恢复备份。
2. 保持两个交易开关为 `false`，按 `docs/release/06-p1a-migration-runbook.md` 先做历史交易号和 JSON 有效性预检。
3. 通过 SSH 隧道执行 P0-B 50 并发与 P1-A 迁移/双 worker 门禁。
4. 无论测试成功或失败，都恢复备份并重新启动测试 API，确认健康检查通过。
5. 重新跑全量后端、JS、迁移和 `git diff --check`，再决定是否提交检查点。

## 回滚

优先保持开关关闭并回退应用；新增表和字段对旧应用为扩展结构，可暂时保留。只有停止所有新应用实例、确认没有处理中回调并导出 `failed/compensation_required` 台账后，才执行 P1-A 单步 downgrade。MySQL DDL 会自动提交，不能假定失败时整体回滚。

本阶段未部署、未连接生产数据库、未调用真实微信支付或退款、未提交、未推送。当前上线判断保持 **NO-GO**。
