# 回滚 Runbook

## 触发条件

候选无法 ready、关键冒烟失败、持续 5xx/延迟异常、登录或报告主流程失败、数据串版、权限/隐私风险、数据库错误增长、容器反复重启或监控不可用时立即停止发布。安全、支付或数据完整性异常不等待观察窗口。

## 应用回滚

1. 停止新功能开关和新后台副作用；不要先删除新容器。
2. 确认 `previous.json` 指向的版本仍在运行且 `/health/ready` 为 200。
3. 设置 `NGINX_UPSTREAM_FILE`、`RELEASE_STATE_DIR`，执行 `scripts/release/rollback.sh`。
4. 脚本校验旧版本、原子恢复 upstream、`nginx -t`、reload，并交换 current/previous。
5. 验证公网登录、报告、海报、DIY、关闭的交易入口、日志和数据库错误。
6. 保存时间线、request ID、镜像 digest、操作者和故障证据；新容器保留到取证结束。

## 数据库处理

应用回滚默认不 downgrade。additive 表/列应与旧应用兼容。只有迁移被明确标记可逆、没有新数据依赖、所有新进程已停止、已有故障后备份且负责人批准时，才执行指定 `--steps` downgrade。

不可逆数据损坏时停止写入，使用已验证备份恢复到新实例，完成校验后再切换数据库。不得直接覆盖原库；恢复范围、RPO 数据损失和对账结果必须记录。优先 forward fix，避免在大表上紧急逆向 DDL。

## 演练

每个候选版本至少在测试环境完成一次 blue -> green -> blue 演练，确认旧容器保留、滚动位置无关的 API 状态、Nginx reload、状态记录和数据库不回退。没有演练证据即 NO-GO。
