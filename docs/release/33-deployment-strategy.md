# 不可变部署策略

## 发布单位

版本格式为 `vYYYYMMDD-NNN[-suffix]`。CI 构建唯一 tag，生产部署只接受 `repository@sha256:<digest>`；禁止 `latest`，禁止服务器现场 build，禁止覆盖源码目录。

## 蓝绿流程

1. CI 通过后执行 `scripts/release/build_image.sh --push`，记录 commit、tag 和 digest。
2. 完成备份、隔离 migration dry run 和环境校验。
3. 选择非活动 slot/port，通过 `deploy_candidate.sh` 拉取摘要镜像并启动。
4. 候选 `/health/live` 和 `/health/ready` 均通过，再执行登录、报告、海报、DIY 和关闭功能冒烟。
5. `switch_traffic.sh` 先校验候选，原子替换 Nginx upstream，执行 `nginx -t` 后 reload。
6. 发布状态原子记录 `current.json` 和 `previous.json`，旧版本在观察窗口内继续运行。
7. 观察结束后才停止旧版本；数据库和日志记录继续保留。

`compose.release.yaml` 不含 build 和数据库容器，只运行预先构建的 API/worker 镜像并加入既有内部网络。物流 worker 不随候选 API 自动启用，避免切流前产生双重副作用。

## 失败

候选启动失败不改流量。切流失败恢复原 Nginx 文件。观察期异常执行 `rollback.sh` 切回 previous；默认不做数据库 downgrade。任何脚本失败都必须停止后续步骤并保存日志与 request ID。
