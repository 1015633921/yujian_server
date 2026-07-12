# 基础指标设计

项目未引入 Prometheus 依赖。`app.observability.MetricsRegistry` 提供线程安全的 counter、duration summary 和 gauge 快照；内部端点默认关闭，开启后还必须使用独立 Bearer 运维令牌。

| 域 | 指标 |
|---|---|
| 登录 | `login_success_total`、`login_failed_total` |
| 报告 | `report_generate_total`、`report_generate_failed_total`、`report_generate_duration` |
| 海报 | `poster_generate_total`、`poster_failed_total` |
| 订单 | `order_create_total`、`order_create_failed_total` |
| 支付 | `payment_callback_total`、`payment_callback_failed_total`，以 callback_type 区分支付/退款 |
| 物流 | `logistics_sync_total`、`logistics_sync_failed_total`；持久结果另存 `runtime_task_runs` |
| 系统 | `api_request_total`、`api_latency`、`api_error_total`、派生 `api_error_rate`、`db_error_total` |
| 外部依赖 | `external_service_failed_total`，仅使用低基数 service/error_type 标签 |

HTTP route 标签使用 FastAPI 模板路径，不使用带订单/报告 ID 的实际 URL，避免高基数和资源 ID 泄露。指标不包含 user ID、request ID、手机号、地址、SKU 或第三方报文。

当前 registry 为单进程内存统计，适合建立接口和本地验证；多 Uvicorn worker 的全局聚合、持久时序存储、采集器和报警规则属于 P1-D。上线前至少需要定义：5xx/error rate、登录失败突增、订单创建失败、支付回调失败、物流连续失败、DB readiness 失败的阈值和通知责任人。
