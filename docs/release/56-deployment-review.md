# 最终部署审计

## 结论

P1-D 已建立候选镜像、环境校验、迁移审计、备份校验、蓝绿切流和回滚设计，但没有针对当前精确代码候选的 CI、镜像、MySQL、Nginx 或回滚演练证据。部署结论为 **BLOCKED / NO-GO**。

## 检查结果

| 检查项 | 状态 | 证据 | 剩余风险 |
| --- | --- | --- | --- |
| CI | BLOCKED | `.github` workflow 包含质量、安全、容器、MySQL 门禁 | 工作流未提交，无法证明对当前代码执行过 |
| 可重复构建 | PASS（静态） | Python/Node 版本、lock/hash、基础镜像 digest 已固定 | Docker 不可用，未生成和核对候选镜像 |
| 镜像版本化 | PASS（设计） | 候选 workflow 和 release state 使用 commit/digest | 无当前候选摘要 |
| 环境隔离 | PASS（静态） | test/prod 小程序配置分离；env validator 防串库并默认关闭交易 | 未在真实候选容器内执行生产 preflight |
| 数据库迁移 | PARTIAL | additive migration；SQLite 往返通过；迁移审计设计存在 | MySQL upgrade/downgrade 未执行 |
| 备份与恢复 | BLOCKED | 备份脚本包含 SHA-256；隔离恢复脚本存在 | 没有实际备份、校验和恢复日志 |
| Nginx 切流 | BLOCKED | `switch_traffic.sh` 原子替换并验证 | 本机无 Nginx，未演练实际配置 |
| 应用回滚 | BLOCKED | `rollback.sh` 可切回 previous digest | 未验证 previous 镜像、健康检查和流量恢复 |
| 监控/告警 | BLOCKED | request_id、健康检查、指标设计存在 | 无集中采集和告警验收 |

## 故障恢复方案

### 应用发布失败

停止切流或执行 `scripts/release/rollback.sh` 切回 release state 中的 previous 镜像；验证公网 live/ready 和关键只读接口。当前仅为设计，必须先演练。

### 数据库迁移失败

在切流前停止发布，保留旧应用和 additive schema；使用迁移审计定位失败。只有经过审批且已完成备份/隔离恢复验证时才执行 downgrade 或恢复，不允许盲目覆盖共享库。

### 支付异常

保持 `WECHAT_PAYMENT_ENABLED=false`、`COMMERCE_CHECKOUT_ENABLED=false`，停止新交易；保留回调和订单证据，按状态机核对后再决定应用回滚。不得通过数据库手工改状态或重复调用真实支付。

## 上线前要求

1. 形成干净候选 commit，并让全部 CI job 对该 commit 全绿。
2. 在隔离 MySQL 完成迁移、并发、备份、校验和恢复。
3. 构建不可变镜像并记录 digest、SBOM/扫描结果。
4. 在预发布环境完成 Nginx 切流与应用回滚演练。
5. 接入集中日志、指标和告警，并确认上线值守责任人。
