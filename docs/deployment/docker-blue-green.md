# Docker 蓝绿统一发布方案

## 使用范围

当前测试和正式环境统一使用 Docker 蓝绿切流、健康检查和回滚。为了避免测试服务器
跨境拉取 GHCR 镜像造成数分钟等待，两种环境采用不同的镜像交付方式：

- 测试环境上传最小后端源码上下文，在服务器按内容哈希构建并复用本地镜像；
- 正式环境继续构建、推送并部署不可变的 `repository@sha256:<digest>` 镜像。

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

代码推送到 `master` 后会自动运行 `deploy-docker-blue-green` 发布测试环境；正式环境仍由
GitHub Actions 手动选择 `prod`。工作流会：

1. 计算最小后端构建上下文的 SHA-256；小程序、素材原图和无关文档不进入服务镜像。
2. 测试发布上传约数 MB 的构建上下文；服务器已有相同哈希镜像时直接复用，没有时使用
   本地 BuildKit 缓存构建，不经过 GHCR。
3. 正式发布构建并推送唯一的 `repository@sha256:<digest>` 镜像，服务器使用临时
   Docker 登录目录拉取，任务结束立即删除登录文件。
4. 上传最小部署控制包并执行 `python3 scripts/deploy.py <env>`，以候选服务 readiness
   作为切流条件。

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

1. 校验环境配置、内容哈希/不可变镜像摘要、release 格式、Docker 网络和证书目录。
2. 初始化环境级发布锁和当前 legacy 状态，不改变流量。
3. 用候选镜像只读检查待执行 migration；没有待执行项时跳过备份与 migration。
   有待执行项时，先使用现有 MySQL 容器执行单库一致性备份并生成 SHA-256 和元数据。
4. 从中央 env 生成不含部署专用凭据的 release env 快照。
5. 以 Nginx 当前 upstream 为准校准发布状态，避免历史手工发布造成状态漂移。
6. 只清理非活动候选槽位的同名历史容器；其他容器占用候选端口时停止发布并报错。
7. 仅在存在待执行项时，使用候选镜像执行版本化、幂等的 MySQL migration。
8. 在非活动 blue/green 槽位拉起候选，只绑定 `127.0.0.1`。
9. 候选 `/health/ready` 必须返回本次 `release_version`。
10. 原子改写该环境 Nginx upstream，执行 `nginx -t` 和 reload。
11. 记录 current/previous，再验证公网 readiness 与 release。
12. 公网验证失败时自动切回 previous；数据库默认不自动 downgrade。

成功后上一版本继续运行，作为快速回滚目标。测试环境保留当前/上一镜像及少量近期缓存，
自动清理更旧的本地测试镜像。

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

正式镜像迁移到腾讯云 TCR 时，在 `prod` Environment 增加：

- Variable `DEPLOY_IMAGE_REPOSITORY`：不带 tag/digest 的完整 TCR 仓库；
- Variable `DEPLOY_REGISTRY_HOST`：TCR 登录域名；
- Secret `DEPLOY_REGISTRY_USER`；
- Secret `DEPLOY_REGISTRY_TOKEN`。

未配置时自动使用 GHCR。部署器通过 `YUJIAN_IMAGE_REPOSITORY` 校验实际仓库，正式环境仍只接受
摘要镜像。TCR 启用前应完成一次构建、推送、服务器拉取和回滚演练；测试环境不依赖这项配置。

## Kubernetes 预留

`deploy/k8s` 暂时只作为未来多节点扩容参考，不参与当前 CI/CD。达到多节点、高可用或多服务编排需求后，
再单独恢复 Kubernetes 发布门禁；当前服务器不安装单机 K3s。
