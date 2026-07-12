# 最终安全审计

## 结论

认证、用户资源隔离和 SSRF 防护的实现及定向测试整体通过，但发现 1 个支付完整性 P0，安全审计结论为 **FAIL / NO-GO**。

## 检查结果

| 检查项 | 状态 | 证据 | 剩余风险 |
| --- | --- | --- | --- |
| 用户资源隔离 | PASS | 私有报告、依据、DIY、地址、购物车、订单接口依赖 `require_current_user`；`tests/test_p0a_security.py` 与定向测试通过 | 仍需在部署候选上做真实双账号 IDOR 验收 |
| Token 生命周期 | PASS | 随机 session token、服务端仅存哈希、TTL/撤销/登出校验；客户端账号切换清理私有缓存 | 未验证多设备和服务重启场景 |
| SSRF | PASS | 远程头像默认关闭；HTTPS/精确白名单/DNS/IP/重定向/大小/类型校验；定向测试通过 | 生产 DNS 与代理行为需部署后复验 |
| Secret | PASS | `scripts/scan_secrets.py` 通过，`pip-audit` 无已知生产依赖漏洞 | 微信开发者工具面板出现 AppSecret 规则项但标记已通过，仍应人工确认上传包 |
| 日志脱敏 | PASS | 定向测试未发现 Token、openid、地址或完整个人信息输出 | 集中日志平台尚未接入，无法审计真实采集配置 |
| 模拟支付/发货 | FAIL | `app/api.py:708`、`:718` 暴露正式 API 路由；`app/order_service.py:1494`、`:1543` 仅依赖 `WECHAT_PAY_TEST_MODE` | 生产误配后，已登录用户可把自己的订单推进为已支付、已发货 |

## P0：生产可路由的模拟交易能力

`/api/v1/orders/{order_id}/mock-pay` 和 `/mock-ship` 没有在路由层检查部署环境、checkout/payment feature flag 或管理员权限。服务层只检查 `WECHAT_PAY_TEST_MODE`。`scripts/validate_release_env.py` 只校验 `COMMERCE_CHECKOUT_ENABLED` 与 `WECHAT_PAYMENT_ENABLED`，未强制生产环境的 `WECHAT_PAY_TEST_MODE=false`。

影响：生产环境一旦误配测试变量，普通订单所有者即可绕过真实支付与履约流程，确认库存预占并篡改订单状态。这属于支付完整性与业务授权绕过，阻止上线。

## 上线前要求

1. 生产构建不注册模拟路由，或路由层强制仅本地/测试环境且启动时 fail closed。
2. 发布环境校验必须拒绝生产 `WECHAT_PAY_TEST_MODE=true`。
3. 增加生产配置与 API 级回归测试，证明模拟路由不可达。
4. 在候选包内再次执行 Secret 扫描，并人工核对小程序上传包。
