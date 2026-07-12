# 上线门禁

## GO 必要条件

- CI quality 和隔离 MySQL jobs 全部通过，clean Docker build 可复现。
- 全量后端、JS、语法、OpenAPI、migration、Secret 和漏洞扫描通过，无新增失败或 skip 门禁。
- P0-A/B、P1-A/B/C 的 MySQL 门禁和人工验收全部关闭。
- 无未关闭 P0/P1；风险所有者、回滚负责人和发布窗口明确。
- test/prod 环境校验通过，Secret 权限、数据库、微信、COS、支付和 feature flags 已双人复核。
- 备份 checksum 与隔离 restore 通过；migration dry run、锁评估和旧应用兼容通过。
- 摘要镜像、commit、版本、SBOM/provenance 可追溯。
- 测试环境候选部署、Nginx 切流、健康、冒烟、监控和应用回滚演练通过。

## 一票 NO-GO

Secret/隐私泄露、测试失败、MySQL gate 缺失、漏洞未处置、构建漂移、环境串线、未知 migration、备份未恢复验证、无可用 previous、回滚未演练、支付/库存/权限风险、监控不可用，任一项即停止。

## 当前状态

当前为 **NO-GO**。本机无 Docker，隔离 MySQL 门禁和真实 Nginx 蓝绿演练尚未执行；全量后端存在一项既有测算测试失败；P1-B 全国地点数据仍不完整。P1-D 完成后仍必须执行最终上线审计，不能自动转为 GO。
