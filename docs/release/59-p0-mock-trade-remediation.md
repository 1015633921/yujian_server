# 最终审计 P0 模拟交易端点整改结果

整改日期：2026-07-12
整改状态：**代码已修复，待候选提交与 CI 复验**
项目整体状态：**NO-GO**

## 原问题

正式 API 注册了 `/api/v1/orders/{order_id}/mock-pay` 和 `/mock-ship`。服务层只依赖 `WECHAT_PAY_TEST_MODE`；发布环境校验没有强制生产关闭该变量。生产误配时，订单所有者可能绕过真实支付和履约状态机入口。

## 整改内容

1. `mock_trade_enabled()` 只允许 `local/development/dev/test/testing` 且显式设置 `WECHAT_PAY_TEST_MODE=true`。
2. `production/prod/staging` 即使误设测试模式也始终返回 false。
3. 两个模拟交易 API 在读取订单前执行门禁；禁用时统一返回 404，不调用订单服务。
4. `WechatPayConfig.test_mode` 复用同一环境门禁，内部直接调用也会 fail closed。
5. 生产启动检查遇到 `WECHAT_PAY_TEST_MODE=true` 时拒绝启动。
6. 发布环境预检要求生产明确配置 `WECHAT_PAY_TEST_MODE=false`，缺失或开启均失败。
7. 生产 compose、候选 release compose 和生产环境示例显式覆盖为 false。

## 回归证据

- P0 最小门禁测试：14 passed。
- API、订单、库存、支付 Webhook、发布工程：128 passed。
- 完整后端：215 passed，4 skipped，1 failed，1 warning。
- 小程序：44 个 JS 文件语法通过，48 个 JS 测试通过。
- `git diff --check`：通过。

唯一完整后端失败仍为整改前已存在的财富愿望推荐主石回归：实际 `green_phantom`，测试期望集合为 `titanium_quartz/citrine/gold_rutilated_quartz/sunstone`。该 P1 与本次 P0 修改无关，但仍阻止项目上线。

## 关闭条件

本 P0 的代码路径已经 fail closed。完成以下两项后可在发布候选上正式关闭：

1. 将整改与相关测试纳入不可变候选 commit。
2. CI 对该精确 commit 全绿，并在候选环境验证生产配置开启测试模式会被预检和启动检查拒绝。

checkout/payment 继续默认关闭，整改期间未连接生产环境，也未调用真实支付、退款或物流。
