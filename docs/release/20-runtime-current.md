# P1-C 运行模型基线

日期：2026-07-12。P1-C 开始时分支为 `codex/material-taxonomy-checkpoint`，HEAD `454668e`，工作区已包含 P0-A 至 P1-B 的未提交修改。本阶段未重置、提交或推送。

## 修改前模型

| 范围 | 现状 | 风险 |
|---|---|---|
| Web 进程 | Dockerfile 启动 Uvicorn `--workers 2` | 每个 worker 都执行 FastAPI lifespan |
| 后台任务 | lifespan 创建 daemon 物流线程，永久 `while True` | 两个 worker 重复同步；异常直接吞掉；进程退出即丢失状态 |
| 单实例任务 | 物流同步、库存过期处理 | 物流无跨进程锁；库存过期已有显式维护入口，不在 worker 内启动 |
| 可水平扩展 | 无状态 HTTP、受数据库唯一约束保护的订单/支付/报告请求 | 后台循环不能随 Web 横向扩展 |
| 数据库 | 每次操作新建 SQLite/PyMySQL 连接；MySQL 有连接/读写超时 | readiness 不探测 DB；部分初始化仍有历史自动建表行为 |
| 外部调用 | 微信 8/12 秒、快递100 10 秒、远程头像 6 秒；COS 未显式配置 timeout | 无统一错误分类、request ID 或失败指标 |
| 日志 | 少量标准 logging；物流线程异常被吞；无统一格式 | 无 request ID，关键链路难串联，异常可能输出底层文字 |
| 错误处理 | validation 和兜底 500；HTTPException 使用框架默认格式 | 错误体不统一，500 路径可能返回内部 detail |
| 健康检查 | `/health` 固定 200，仅展示环境和数据库类型 | DB 不可用时仍可能接流量 |
| 指标 | 无统一 registry | 登录、报告、订单、支付、物流无法量化告警 |

修改前全量后端基线为 `180 passed, 3 skipped, 1 failed`，JS 为 `47 passed`。唯一失败是早已存在的财富愿望主石断言，实际返回 `green_phantom`。

## 修改后模型

- Web：两个或更多 Uvicorn worker 只处理 HTTP，不创建 scheduler/thread/daemon。
- Logistics worker：`python -m app.logistics_worker` 独立进程；开关关闭时在连接数据库前退出。
- 协调：`runtime_task_leases` 条件更新提供跨进程调度窗口租约；`runtime_task_runs` 保存非敏感运行结果。
- 追踪：客户端合法 request ID 优先，否则服务端生成；注入 response header、logger context 和下游调用。
- 日志：应用事件统一 JSON；用户 ID 只保存加盐摘要；请求体和敏感字段不进入日志。
- 健康：liveness 不访问依赖；readiness 只检查数据库、启用功能所需迁移表和必要配置，不访问微信/快递/COS。
- 指标：进程内 registry 记录 HTTP、登录、报告、海报、订单、支付和外部失败；物流另有持久任务运行表。

仍需单实例或租约的任务：物流同步。订单、支付事件、报告生成可横向扩展，依赖各自数据库幂等/唯一约束。第三方写操作不能做无边界自动重试；物流查询只重试失败订单且最多 3 次。
