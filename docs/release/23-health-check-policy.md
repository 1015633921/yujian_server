# 健康检查策略

| 路径 | 用途 | 依赖 | 失败语义 |
|---|---|---|---|
| `/health` | 旧探针兼容 | 无 | 服务进程可响应即 200 |
| `/health/live` | liveness | 无 | 进程事件循环/路由不可响应才失败 |
| `/health/ready` | readiness | 数据库、迁移表、启用功能配置 | 不可接流量时返回 503 |

readiness 使用只读连接执行 `SELECT 1`，不会调用微信、快递100、COS 或 CDN。SQLite 探针以只读模式打开且不会偷偷创建数据库文件。MySQL 探针不调用应用的自动 Schema 初始化。

始终要求 `schema_migrations`。只有对应 Feature Flag 开启时才检查订单预占、支付事件或报告快照表。支付开启时检查 AppID、商户号、序列号、私钥、APIv3 key 和通知地址是否存在，但不输出值。生产还要求 `LOG_HASH_SALT`；指标端点开启时要求独立访问令牌。

readiness 响应只暴露组件状态、缺失配置名和缺失表名，不返回数据库主机、账号、密码或异常原文。数据库错误增加 `db_error_total`。

Compose 的 API healthcheck 改用 `/health/ready`。liveness 与 readiness 的容器编排细分、启动宽限和流量摘除策略在 P1-D 部署阶段最终确认。
