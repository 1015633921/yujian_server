# 回滚 Runbook

出现持续 5xx、关键流程失败、支付或订单状态异常、数据库错误增长、隐私风险或容器反复重启时，
立即停止继续发布。

```bash
python3 scripts/deploy.py test rollback
python3 scripts/deploy.py prod rollback
```

命令先验证 previous 的 localhost readiness，再切换该环境独立的 Nginx upstream 并验证公网；
公网验证失败会恢复原流量且不交换状态。应用回滚不会自动执行数据库 downgrade。

只有迁移明确可逆、没有新数据依赖、所有新进程已停止、已有故障后备份且负责人批准时，
才允许指定 steps 执行 downgrade。不可逆数据问题应停止写入并恢复到新数据库实例，禁止直接覆盖原库。

每个正式候选必须先在测试环境完成 blue -> green -> blue 演练并保存 release、镜像 digest、
健康检查和回滚结果。
