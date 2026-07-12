# P0-A 数据库迁移手册

## 设计说明

项目使用原生 SQL 和自有 SQLite/MySQL 连接封装，没有 SQLAlchemy ORM。为避免为一次安全迁移引入新的生产依赖，本阶段增加项目内版本化迁移运行器 `app.migrations.runner`。迁移不会在应用启动时自动执行。

版本 `20260712_01_p0a_security` 只做扩展：

- 新增 `user_sessions`，数据库只保存访问令牌 SHA-256 摘要。
- 为 `diy_designs` 新增 `share_status`、`share_token_hash`、`share_published_at`、`share_revoked_at`。
- 新增会话查询索引和分享令牌唯一索引。
- 不删除、重命名或改写既有字段与业务数据。

## 上线前升级

1. 确认四个风险开关、`ALLOW_DEV_WECHAT_LOGIN` 和 `TRUST_CLOUDBASE_IDENTITY_HEADERS` 均为 `false`。只有在请求必经受信 CloudBase 网关并隔离直连入口时，才可单独评审后者。
2. 备份目标数据库并记录备份标识。
3. 在与应用相同的环境变量下运行迁移，不启动应用流量。

SQLite 演练：

```bash
.venv_codex/bin/python -m app.migrations.runner upgrade --backend sqlite --sqlite-path /tmp/yujian-p0a.db
```

MySQL 测试环境：

```bash
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner upgrade --backend mysql
```

4. 再次执行 upgrade，结果必须为 `no changes`。
5. 检查 `schema_migrations` 已记录 `20260712_01_p0a_security`。
6. 检查 `user_sessions` 和四个分享字段存在，令牌字段未出现明文。
7. 完成应用冒烟后再逐步放量。P0-A 本身不授权开启结算、公共分享、远程头像抓取或物流同步。

## 回退

优先回退应用版本并保持所有风险开关关闭。新增表和字段不会影响旧应用，可暂时保留，这是推荐的低风险回退方式。

只有在确认没有新版本应用实例、无需保留任何新会话和分享状态后，才执行结构回退：

```bash
.venv_codex/bin/python -m app.migrations.runner downgrade --backend sqlite --sqlite-path /tmp/yujian-p0a.db
DATABASE_BACKEND=mysql .venv_codex/bin/python -m app.migrations.runner downgrade --backend mysql
```

结构回退会删除本迁移新增的会话表和分享字段，不会删除既有业务表。生产执行前仍需单独审批和备份验证。

## 后续事项

项目其他历史表仍有启动时 DDL；本阶段没有扩大范围清理，列为 P1 数据库治理事项。
