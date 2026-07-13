# 快递100主动订阅上线手册

## 目标与边界

发货成功后，服务端向快递100订阅接口提交快递公司、单号、回调地址和必要的手机号后四位。快递100有新轨迹时回调本服务；用户打开订单时的实时查询继续保留，作为订阅失败、推送延迟和历史订单的兜底。

订阅状态、回调摘要和轨迹保存在 `orders.logistics_json` 中。签收后自动完成使用迁移 `20260713_07_order_receipt_completion` 新增的 `logistics_signed_at` 和 `auto_complete_at` 索引字段，发布前必须先完成备份与迁移验证。

## 环境变量

```text
KUAIDI100_SUBSCRIBE_ENABLED=false
KUAIDI100_CUSTOMER=<实时查询 customer>
KUAIDI100_KEY=<授权 key>
KUAIDI100_CALLBACK_URL=https://api.example.com/api/v1/logistics/kuaidi100/callback
KUAIDI100_CALLBACK_SALT=<至少 16 位随机值，建议 32 位以上>
KUAIDI100_SUBSCRIBE_RESULTV2=1
KUAIDI100_REQUEST_TIMEOUT_SECONDS=10
```

- `KUAIDI100_SUBSCRIBE_ENABLED` 缺失时为 `false`。
- 回调验签不依赖订阅开关。关闭新订阅后，必须继续保留原 `KUAIDI100_CALLBACK_SALT`，让已登记订阅仍可安全回调。
- 生产回调必须使用 HTTPS。启用前需向快递100确认当前账号已开通 HTTPS 回调支持。
- 回调盐、授权 key 和 customer 不得写入 Git、响应、日志或 `logistics_json`。

## 上线顺序

1. 部署应用，保持 `KUAIDI100_SUBSCRIBE_ENABLED=false`。
2. 配置 customer、key、HTTPS callback URL 和随机 callback salt。
3. 运行发布环境校验并确认 `/health/ready` 正常。
4. 使用本地构造的签名回调验证入口：正确签名返回 `returnCode=200`，错误签名返回 HTTP 401。不得使用真实客户单号做冒烟测试。
5. 在快递100侧确认 HTTPS 回调能力后，显式设置 `KUAIDI100_SUBSCRIBE_ENABLED=true` 并滚动重启 API。
6. 使用一笔非敏感测试发货验证订阅登记、轨迹推送、重复回调和用户端兜底查询。
7. 观察 `logistics_subscription_total`、`logistics_callback_total` 和 `external_service_failed_total`。

## 运行行为

- 后台发货先提交本地发货状态，再登记快递100订阅。第三方失败不会撤销已发货状态。
- 相同订单、相同单号已处于 `active` 或 `completed` 时不会重复提交订阅。
- 后台可调用 `POST /api/v1/admin/orders/{order_id}/logistics/subscribe` 重试失败订阅。
- 回调按 `MD5(param + salt)` 大写摘要验签，并核对回调中的快递单号与快递公司。
- 回调事件摘要最多保留 50 个，用于重复回调去重；轨迹按时间合并并去重。
- 旧回调和兜底查询都不能把已签收状态回退为运输中。
- `shutdown` 且已签收时，只记录 `signed_at` 和签收后 7 天的 `auto_complete_at`，订单仍保持 `shipped`。
- 用户点击确认收货后立即转为 `completed`；未确认时，独立物流 worker 在签收满 7 天后幂等自动完成。
- 自动完成依赖 `LOGISTICS_SYNC_ENABLED=true` 的独立 worker，不在 Uvicorn worker 内启动线程。
- `abort` 会保留服务商原因并继续允许用户端实时查询兜底，不会自动完成订单；相同单号至少等待 30 分钟才允许人工重新订阅。

## 回滚

1. 设置 `KUAIDI100_SUBSCRIBE_ENABLED=false`，停止登记新订阅。
2. 保留回调路由、callback salt 和现有物流查询配置，直到在途订阅全部结束。
3. 用户打开订单时仍通过原实时查询获得最新轨迹；必要时继续运行独立物流同步任务。
4. 应用代码需要回退时，保留 additive 字段和 `logistics_json` 中新增键，旧版本会忽略未知字段。

应用回滚默认不执行数据库 downgrade。不要通过手工覆盖 `logistics_json` 清除订阅状态或轨迹。
