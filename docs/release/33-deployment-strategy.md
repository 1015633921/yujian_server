# 不可变部署策略

## 发布单位

版本格式为 `vYYYYMMDD-NNN[-suffix]`。CI 构建唯一 tag，部署只接受
`repository@sha256:<digest>`；禁止 `latest`、服务器现场 build 和覆盖源码目录。

## Docker 蓝绿流程

测试和正式环境统一执行 `scripts/deploy.py <test|prod>`。脚本自动选择非活动槽位，固定顺序为：

1. 校验摘要镜像、环境配置、证书目录、Docker 内部网络和 Nginx 配置。
2. 拉取镜像并核对 OCI release label。
3. 单库备份，随后使用候选镜像执行幂等 migration。
4. 启动非活动槽位，只绑定 localhost；验证 live/ready 和 release。
5. 原子更新环境独立的 Nginx upstream，`nginx -t` 成功后 reload。
6. 记录 current/previous，验证公网 release；失败自动切回 previous。
7. 上一版本在观察窗口内继续运行，作为快速应用回滚目标。

`compose.release.yaml` 不含 build 和数据库容器。中央 env 会生成权限为 `600` 的版本快照，
`MYSQL_ROOT_PASSWORD` 等部署专用凭据不会传给 API 容器。

数据库默认不自动 downgrade。完整操作说明见 `docs/deployment/docker-blue-green.md`。
