# 发布 Runbook

1. 确认目标 commit 和变更范围；CI 可异步运行，不阻塞部署。
2. 在 GitHub Actions 运行 `deploy-docker-blue-green`，只选择 `test` 或 `prod`。
3. 工作流校验仓库与 CDN 清单，构建摘要镜像，并在服务器执行统一部署命令。
4. 部署命令自动完成备份、migration、候选启动、健康检查、Nginx 切流和公网验证。
5. 测试环境完成登录、订单、售后、后台审核和支付只读状态冒烟后，才允许审批正式环境。
6. 正式切流后观察 5xx、延迟、数据库连接、容器重启、支付回调和资源水位。

部署机只读检查：

```bash
python3 scripts/deploy.py test plan
python3 scripts/deploy.py test status
python3 scripts/deploy.py prod status
```

禁止直接调用低层 Nginx 切流脚本、服务器现场构建或手改 release env。完整说明见
`docs/deployment/docker-blue-green.md`。
