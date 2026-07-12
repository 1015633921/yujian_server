# 最终风险登记册

| ID | 级别 | 风险 | 证据 | 上线条件 |
| --- | --- | --- | --- | --- |
| FINAL-P0-01 | P0 | 生产可路由的模拟支付/发货能力可在测试变量误配时绕过真实交易 | `app/api.py:708`、`:718`；`app/order_service.py:1494`、`:1543`；发布校验未拒绝生产 test mode | 生产构建不可达或启动 fail closed，并有 API/配置回归测试 |
| FINAL-P1-01 | P1 | 98 项关键修改未形成不可变候选，CI 无法证明审计的是发布代码 | `git status --short`：43 modified + 55 untracked | 干净候选 commit、全绿 CI、候选镜像 digest 一致 |
| FINAL-P1-02 | P1 | 完整后端存在核心推荐算法回归 | `test_energy.py` 失败，204 passed / 1 failed | 修复并通过完整回归 |
| FINAL-P1-03 | P1 | MySQL 行锁、并发、事务和迁移门禁未执行 | 4 个 MySQL gate skipped；本机无 Docker/MySQL | 隔离 MySQL 全部门禁通过 |
| FINAL-P1-04 | P1 | 候选构建、Nginx 切流、备份恢复和回滚未演练 | Docker/Nginx 不可用，无执行日志 | 预发布全流程演练通过 |
| FINAL-P1-05 | P1 | 报告 V2 默认关闭，发布默认值不提供已宣称的版本/快照保证 | `REPORT_VERSIONING_V2_ENABLED=false` | MySQL 验收后明确启用或调整产品承诺 |
| FINAL-P1-06 | P1 | 校准可信地点仅 11 条，无法覆盖前端地点范围 | `docs/release/13-location-calibration-policy.md` | 限制支持范围或补充可靠坐标数据 |
| FINAL-P1-07 | P1 | 权威 SKU 价格源仍为 MySQL `DOUBLE` | `app/database.py:167` | 使用整数分/DECIMAL 并完成迁移校验 |
| FINAL-P1-08 | P1 | 生产约束下的小程序核心链路和设备矩阵未通过 | 开发工具有 timeout；域名/TLS 校验关闭 | 真实测试域名、设备矩阵和异常状态验收通过 |
| FINAL-P1-09 | P1 | 无集中日志、指标与告警的实证 | 仅有进程内指标和设计文档 | 接入并演练关键告警与值守 |
| FINAL-P2-01 | P2 | 小程序存在大于 200KB 资源 | 微信开发者工具代码质量面板 | 压缩/拆包并确认上传包限制 |
| FINAL-P2-02 | P2 | 图片可访问名称和大字体证据不足 | 开发工具可访问树及人工检查 | 补齐语义并完成无障碍验收 |
| FINAL-P2-03 | P2 | CORS 为宽泛允许配置 | 后端 CORS 配置 | 按实际小程序/管理端来源收敛 |
| FINAL-P2-04 | P2 | legacy source-build compose 与正式 release compose 并存 | `compose.yaml`、`compose.release.yaml` | 发布权限和 runbook 强制只用 release path |
| FINAL-P3-01 | P3 | runbook 写“两个 job”，实际 CI 已扩展 | `docs/release/36-release-runbook.md:8` | 文档同步 |
| FINAL-P3-02 | P3 | README 的工具链与部分业务描述滞后 | `README.md` 与锁文件/现实现不一致 | 发布后文档清理 |

## 汇总

- P0：1
- P1：9
- P2：4
- P3：2

只要 P0 或任一 P1 未关闭，最终结论保持 NO-GO。
