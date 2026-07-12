# 物流任务运行设计

## 旧方案

每个 FastAPI worker 在 lifespan 内创建一个 daemon thread。Docker 默认两个 Uvicorn worker，因此同一批运输中订单至少被扫描两次；没有跨进程锁、任务运行记录、失败指标或可审计重试。

## 新方案

```text
Uvicorn worker x N -> HTTP only

logistics-worker process x N
  -> LOGISTICS_SYNC_ENABLED gate
  -> conditional DB lease(runtime_task_leases)
  -> one winner per lease window
  -> refresh max 50 shipped orders
  -> retry failed order IDs only, max 3 attempts
  -> runtime_task_runs + JSON log + metrics
```

启动命令：`python -m app.logistics_worker`；单次调度可用 `--once`。Compose 提供独立 `logistics-worker` service，但开关默认 false。

租约使用任务名主键和原子条件更新 `lease_until <= now`。默认间隔 1800 秒，租约至少为两倍间隔且不低于 3600 秒，覆盖 50 个订单和有限重试的最坏运行窗口。成功后不提前释放租约，防止另一个刚启动的 worker 在同一窗口重复执行；进程崩溃后租约到期自动恢复。

快递查询是只读操作；成功结果按订单覆盖更新，签收状态只在订单仍为 shipped 时转换，因此重试不会重复完成订单。重试只针对明确失败订单，指数等待上限 8 秒，最多 3 次，不无限重试。

失败记录只保存错误类型、checked/failed/attempt 数量，不保存快递单号、手机号、地址或第三方报文。第三方超时固定 10 秒。

回滚时先将 `LOGISTICS_SYNC_ENABLED=false` 并停止独立 worker。Web API 不依赖该进程，可继续运行。新增表可保留；只有已备份、停止所有 worker 后才单步 downgrade P1-C 迁移。
