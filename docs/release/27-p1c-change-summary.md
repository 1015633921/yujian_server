# P1-C 改造摘要

当前结论：**P1-C BLOCKED，项目整体 NO-GO。** 本地代码已达到预期运行模型，剩余阻塞是 MySQL 租约门禁和容器/测试环境运行验收。

## 修改文件与架构

- `app/observability.py`：request context、JSON 脱敏 formatter、事件日志、Metrics registry。
- `app/runtime_health.py`：只读 DB readiness 和启用功能配置检查。
- `app/runtime_tasks.py`、`app/logistics_worker.py`：独立物流进程、数据库租约、有限重试和任务记录。
- `app/main.py`：移除 Web 内物流线程，增加追踪中间件、安全异常、live/ready/metrics。
- `app/api.py`：登录、报告、海报、订单、支付/退款指标和结构化事件。
- `app/order_service.py`：物流失败分类、失败订单列表、第三方超时日志和下游 request ID。
- `auth_service.py`、`wechat_trade_service.py`、`avatar_storage.py`：超时、request ID、错误分类和 COS 显式 timeout。
- `miniprogram/utils/api.js`：每次请求生成安全 request ID，网络重试复用。
- `compose.yaml`：新增独立 logistics-worker；API healthcheck 切换 readiness。
- v05 migration：新增 `runtime_task_leases` 与 `runtime_task_runs`，additive 且可单步回退。

## 运行与回滚

Web worker 可以水平扩展；物流 worker 也可多实例部署，但同一租约窗口只有一个执行。开关关闭时独立 worker 在连接数据库前退出，API 不受影响。

止损顺序：先设 `LOGISTICS_SYNC_ENABLED=false` 并停止物流进程；指标异常时设 `METRICS_ENDPOINT_ENABLED=false`；API 可继续运行。若观测中间件需要应用回退，新表保持不动即可兼容旧应用。只有停止全部新进程并完成整库备份后才 downgrade v05。

## 剩余风险

1. MySQL 租约并发和 v05 DDL 尚未在备份后的共享测试库验证。
2. 本机无 Docker CLI，Compose 官方解析、容器健康检查和进程重启尚未实测。
3. Metrics 为每进程内存统计；跨 worker 聚合、持久化、告警和 SLO 属于 P1-D。
4. Nginx/Uvicorn 自身日志仍需在部署层统一 JSON 和敏感 header 策略。
5. P1-B 全国地点数据仍是既有阻塞，财富愿望主石测试仍是既有失败。

下一阶段 P1-D 应处理依赖锁定、CI/CD、容器运行验收、迁移发布编排、日志/指标采集、报警、生产配置审查和可演练回滚。当前不得灰度或上线。
