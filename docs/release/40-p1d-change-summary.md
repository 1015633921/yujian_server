# P1-D 改造摘要

## CI 与依赖

- 新增 GitHub quality/MySQL gate 和受 CI 成功约束的候选镜像 workflow。
- Python 直接依赖精确固定，传递依赖带 hash lock；Node/npm 版本和 lock 固定。
- `cryptography` 从存在已知漏洞的 `46.0.7` 升级到修复版 `48.0.1`，复扫无已知生产依赖漏洞。
- 新增工具链、Secret、仓库文件、环境隔离、小程序语法和镜像引用检查。

## 构建与部署

- Docker 基础镜像固定 digest，生产依赖 `--require-hashes`，容器使用非 root UID，写入 OCI 版本/commit label。
- MySQL 镜像固定 digest；新增无 build 的 `compose.release.yaml`。
- 新增候选构建、预检、部署、Nginx 切流、发布状态和回滚脚本。
- 旧 SSH 覆盖脚本保留，但不再内置服务器/密钥路径，生产默认阻止。

## 环境与迁移

- test/prod 小程序配置彻底分离；后端 env validator 不输出值并阻止串库、缺项和交易开关误开。
- test/prod 启动缺关键配置时拒绝启动；生产运行时 DDL/seed/backfill 默认关闭。
- migration 增加操作者、release 和不可变历史；备份增加 SHA-256；提供 SQLite/MySQL 往返和隔离恢复入口。

## 兼容与回滚

业务 API、测算、支付、库存和物流语义未在 P1-D 改动。应用回滚只切回 previous 摘要镜像，默认保留 additive schema；数据库 downgrade 需要额外审批和备份。

当前 checkout/payment 继续默认关闭。由于 Docker/MySQL/Nginx 运行验收、既有测试失败和上游 P1 阻塞未关闭，整体仍为 NO-GO。
