# Docker 蓝绿统一发布方案

## 使用范围

当前测试和正式环境统一使用 Docker 蓝绿发布。操作者只选择 `test` 或 `prod`，其余步骤、
镜像格式、健康检查和回滚逻辑完全相同。

| 环境 | 公网入口 | 数据库约束 | 蓝/绿端口 |
| --- | --- | --- | --- |
| test | `https://api.yustream.cn/test-api/` | `MYSQL_DATABASE` 必须是独立测试库 | `127.0.0.1:8011/8012` |
| prod | `https://api.yustream.cn/` | 数据库名不得包含 test/dev/local | `127.0.0.1:8021/8022` |

端口只绑定服务器回环地址，公网始终通过现有 Nginx 访问。MySQL 继续位于
`yujian_server_backend` 内部 Docker 网络，不开放新的公网端口。

## 配置收敛

- `deploy/environments/<env>.json`：非敏感部署拓扑，包括端口、Nginx upstream、状态目录和健康地址。
- `/opt/yujian/config/<env>.env`：唯一人工维护的环境配置，权限必须为 `600`，不进入 Git 和镜像。
- `/opt/yujian/runtime/<env>/<release>.env`：部署时生成的不可变运行快照，权限为 `600`；
  `MYSQL_ROOT_PASSWORD` 等仅部署凭据不会传入 API 容器。
- `/opt/yujian/releases/state/<env>/current.json` 与 `previous.json`：不含 Secret 的当前和上一版本状态。
- `miniprogram/config/asset-manifest.json`：小程序 CDN 静态资源的统一逻辑清单。

测试和正式环境不得共用数据库。切换小程序本地调试环境时仍使用
`node scripts/select_miniprogram_env.js test|prod`，不要手改生成文件。

## 日常发布

GitHub Actions 中运行 `deploy-docker-blue-green`，只选择目标环境。工作流会：

1. 构建并推送唯一的 `repository@sha256:<digest>` 镜像。
2. 上传最小部署控制包，不上传源码或环境配置。
3. 使用临时 Docker 登录目录在服务器拉取镜像，任务结束立即删除登录文件。
4. 执行 `python3 scripts/deploy.py <env>`，以候选服务 readiness 作为切流条件。

完整 CI 继续异步运行并提供反馈，但不作为部署前置条件，方便测试环境快速迭代。

服务器命令也保持一致：

```bash
python3 scripts/deploy.py test plan
python3 scripts/deploy.py test status
python3 scripts/deploy.py prod status

APP_IMAGE='ghcr.io/1015633921/yujian_server/api@sha256:<digest>' \
RELEASE_VERSION='v20260714-001-example' \
python3 scripts/deploy.py test
```

首次部署某环境时，脚本会把现有 Nginx 直连端口无损转换为该环境的独立 upstream，
先执行 `nginx -t` 再 reload。转换失败会恢复原配置；测试和正式 upstream 文件相互独立。

## 固定发布顺序

1. 校验环境配置、不可变镜像摘要、release 格式、Docker 网络和证书目录。
2. 初始化环境级发布锁和当前 legacy 状态，不改变流量。
3. 使用现有 MySQL 容器执行单库一致性备份并生成 SHA-256 和元数据。
4. 从中央 env 生成不含部署专用凭据的 release env 快照。
5. 使用候选镜像执行版本化、幂等的 MySQL migration。
6. 在非活动 blue/green 槽位拉起候选，只绑定 `127.0.0.1`。
7. 候选 `/health/ready` 必须返回本次 `release_version`。
8. 原子改写该环境 Nginx upstream，执行 `nginx -t` 和 reload。
9. 记录 current/previous，再验证公网 readiness 与 release。
10. 公网验证失败时自动切回 previous；数据库默认不自动 downgrade。

成功后上一版本继续运行，作为快速回滚目标。下一次发布复用非活动槽位，不在服务器现场构建镜像。

## 回滚

```bash
python3 scripts/deploy.py test rollback
python3 scripts/deploy.py prod rollback
```

回滚前先检查 previous 的本机 readiness；切流后再检查公网。公网检查失败会恢复原流量，
状态文件不会交换。数据库迁移不自动回退；只有迁移明确可逆、已备份并完成独立审批时才执行 downgrade。

## GitHub Environment 配置

`test` 和 `prod` Environment 分别配置：

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_PRIVATE_KEY`
- `DEPLOY_SSH_KNOWN_HOSTS`

正式 Environment 应开启人工审批。工作流使用仓库 `GITHUB_TOKEN` 临时拉取同仓库 GHCR 镜像，
不会把 Token 写入发布目录、命令参数或应用日志。

## Kubernetes 预留

`deploy/k8s` 暂时只作为未来多节点扩容参考，不参与当前 CI/CD。达到多节点、高可用或多服务编排需求后，
再单独恢复 Kubernetes 发布门禁；当前服务器不安装单机 K3s。
