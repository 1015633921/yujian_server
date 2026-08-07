# 环境配置策略

dev、test、prod 使用独立 env 文件、数据库名、API、COS、微信与支付配置。Secret 只由部署平台注入，不能进入 Git、镜像 label、命令输出或发布状态文件。

## 强制规则

- test 数据库名必须明确包含 `test`，prod 禁止 `test/local/dev`。
- 小程序 test 只能使用 `/test-api` 和 test CDN；prod 配置不得包含 test endpoint。
- 后端 test/prod 必须使用 MySQL，并显式提供 host、port、database、user 和 password。
- test/prod 必须提供规范 `RELEASE_VERSION` 和非公开 `LOG_HASH_SALT`。
- `ALLOW_RUNTIME_SCHEMA_MUTATION=false`；生产进程不得启动时建表、改列或 seed。
- `COMMERCE_CHECKOUT_ENABLED` 缺省必须为 false；仅在订单幂等、权威定价、库存预占和迁移门禁通过后，才允许生产环境显式开启。
- `WECHAT_PAYMENT_ENABLED` 缺省必须为 false。只有商户签名、回调验签材料、API v3 Key、HTTPS 回调和支付状态机门禁全部通过后，才允许生产环境显式开启；开启建单不等于自动开启真实支付。
- dev 微信登录和 CloudBase 身份头在 test/prod 必须关闭。
- 微信、COS 配置组只允许全有或全无；指标开启时必须有独立 token。

`scripts/validate_release_env.py` 在不显示值的前提下检查 env；`app.runtime_health.assert_startup_configuration` 让 test/prod 缺少关键配置时拒绝启动。示例文件只有占位符，不是可部署配置。

当前没有 Redis 依赖；引入前必须先增加独立实例/namespace、required config 和串线测试，不能复用未声明的生产连接。

## 测试环境 MySQL 公网入口

- `MYSQL_HOST=gz-cynosdbmysql-grp-8glxizb3.sql.tencentcdb.com`
- `MYSQL_PORT=25460`

此入口仅用于测试环境；`MYSQL_DATABASE` 必须为明确包含 `test` 的库名。账号、密码和任何连接 URI 都只能由部署环境或本机私有环境文件注入，禁止提交到仓库。
