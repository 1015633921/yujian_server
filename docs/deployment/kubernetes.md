# Kubernetes 未来扩容预案（当前未启用）

当前测试和正式环境使用 Docker 蓝绿发布，入口、配置和回滚说明见
[`docker-blue-green.md`](docker-blue-green.md)。现有服务器不安装单机 K3s，`deploy/k8s` 不参与当前 CI/CD。

保留 Kustomize 清单是为了未来出现以下条件时复用：

- 增加到多个计算节点并需要主机级故障转移；
- 后端拆分为多个需要独立扩缩容的常驻服务；
- 团队具备 Kubernetes 监控、证书、备份和故障处理能力。

重新启用前必须单独完成容量评估、MySQL 私网连通、Ingress 与现有 Nginx 的边界设计、
Secret 管理、PodDisruptionBudget、滚动回滚演练和多节点高可用验证。不得直接在正式单机上
安装 K3s 后迁流，也不得复用当前 Docker 发布状态文件冒充 Kubernetes revision。
