# 环境配置策略

dev、test、prod 使用独立 env 文件、数据库名、API、COS、微信与支付配置。Secret 只由部署平台注入，不能进入 Git、镜像 label、命令输出或发布状态文件。

## 强制规则

- test 数据库名必须明确包含 `test`，prod 禁止 `test/local/dev`。
- 小程序 test 只能使用 `/test-api` 和 test CDN；prod 配置不得包含 test endpoint。
- 后端 test/prod 必须使用 MySQL，并显式提供 host、port、database、user 和 password。
- test/prod 必须提供规范 `RELEASE_VERSION` 和非公开 `LOG_HASH_SALT`。
- `ALLOW_RUNTIME_SCHEMA_MUTATION=false`；生产进程不得启动时建表、改列或 seed。
- 当前 `COMMERCE_CHECKOUT_ENABLED` 和 `WECHAT_PAYMENT_ENABLED` 必须为 false。
- dev 微信登录和 CloudBase 身份头在 test/prod 必须关闭。
- 微信、COS 配置组只允许全有或全无；指标开启时必须有独立 token。

`scripts/validate_release_env.py` 在不显示值的前提下检查 env；`app.runtime_health.assert_startup_configuration` 让 test/prod 缺少关键配置时拒绝启动。示例文件只有占位符，不是可部署配置。

当前没有 Redis 依赖；引入前必须先增加独立实例/namespace、required config 和串线测试，不能复用未声明的生产连接。
