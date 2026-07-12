# 发布 Runbook

本 Runbook 只允许上线负责人在最终审计通过后执行。示例变量均为占位符，禁止把 Secret 写入命令历史或文档。

## 发布前

1. 确认 release commit、`vYYYYMMDD-NNN` 版本和变更范围冻结。
2. 确认 GitHub `release-quality-gate` 两个 job 全绿、无 P0/P1、漏洞与 Secret 扫描通过。
3. 确认 checkout/payment 等受控功能保持关闭，环境校验通过。
4. 显式设置 `BACKUP_DATABASE`、`RELEASE_VERSION`、`MIGRATION_OPERATOR` 后执行 `backup_mysql.sh`，保存文件、`.sha256`、`.meta`、备份 ID、时间和操作者。脚本一次只备份一个指定数据库。
5. 把备份恢复到隔离库，执行 `verify_mysql_backup_restore.sh`。
6. 在隔离副本执行 `check_migrations.py --backend mysql`，记录耗时、锁和往返结果。
7. 确认 Nginx active upstream、当前/上一 release、空闲 slot/port 和磁盘余量。

## 构建

通过 `build-release-candidate` workflow 构建并推送唯一 tag。记录输出的 `repository@sha256:digest`、commit、SBOM/provenance 和 CI run URL。服务器禁止现场 build。

## 部署候选

设置 `APP_SLOT`、`APP_PORT`、`APP_IMAGE`、`RELEASE_VERSION`、`ENVIRONMENT`、`ENV_FILE`、`CERTS_DIR`、`BACKEND_NETWORK` 后执行：

```bash
scripts/release/preflight.sh
scripts/release/deploy_candidate.sh
```

脚本会校验摘要、env、镜像 release label、拉取镜像、启动非活动 slot，并等待 live/ready。失败时不切流。

## 冒烟与切流

对候选 localhost 端口验证：登录、报告生成、依据页、海报脱敏、DIY 推荐与编辑；确认订单和支付入口仍关闭；检查 JSON 日志、request ID、readiness 和错误率。不得调用真实支付或物流。

冒烟通过后设置 `PROJECT` 和 `NGINX_UPSTREAM_FILE`，执行 `switch_traffic.sh`。立即验证公网 live/ready 和关键只读路径，确认 current/previous 状态文件正确。

## 观察

至少观察约定窗口，检查 5xx、P95、登录失败、报告失败、数据库连接、容器重启和资源水位。异常达到 `38-release-gate.md` 阈值立即回滚。观察期结束并完成负责人签字后，才停止上一 API；物流 worker 需单独、单实例切换和验收。
