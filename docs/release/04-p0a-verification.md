# P0-A 验证记录

验证日期：2026-07-12。结论：P0-A 自动化门禁通过；项目整体仍为 **NO-GO**。

## 命令与真实结果

| 命令 | 结果 |
|---|---|
| `git status --short`、`git branch --show-current`、`git log -5 --oneline` | 分支 `codex/material-taxonomy-checkpoint`；既有未提交报告页等修改保留；未提交、未推送 |
| `.venv_codex/bin/python -m py_compile ...` | 通过 |
| `node --check`（全部 `miniprogram/**/*.js`） | 通过 |
| `pytest -q tests/test_p0a_security.py tests/test_p0a_migrations.py tests/test_api.py -p no:cacheprovider` | `77 passed, 1 warning` |
| `pytest -q --ignore=tests/minium -p no:cacheprovider` | `109 passed, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `36 passed, 0 failed` |
| SQLite CLI：upgrade、重复 upgrade、downgrade、再次 upgrade | 依次为迁移成功、`no changes`、回退成功、再次迁移成功 |
| OpenAPI 生成与安全声明断言 | 通过，共 118 个路径；私有 profile 有 HTTP Bearer，材料和 token 分享读取无 Bearer 要求 |
| Compose 与 `.env.local.example` 四个风险开关检查 | 全部默认 `false` |
| 变更凭据模式扫描 | 未发现新增凭据模式 |
| `git diff --check` | 通过 |
| `docker info`、`docker compose ps` | 未执行 MySQL 验证：本机没有 `docker` 命令 |

Minium 按项目规则未运行。没有连接生产数据库，没有部署，没有调用真实微信支付、退款、短信或物流。

## 基线既有失败

```text
tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements
expected titanium_quartz/citrine/gold_rutilated_quartz/sunstone
actual green_phantom
```

该失败在 P0-A 修改前已经存在。本阶段新增失败：**0**。

另有一个 Starlette `TestClient` 关于 `httpx2` 的依赖弃用警告，不影响本阶段行为验证，后续按依赖升级窗口处理。

## 自动化覆盖

- 正常登录、缺失/伪造/过期/撤销 Token、退出后失效、数据库仅存 Token hash。
- dev 身份回退和未受信 CloudBase 身份头默认拒绝。
- 用户 A/B 对 profile、报告/依据数据、DIY、收藏/购物车、地址、订单和售后的越权负向路径。
- 私有 DIY 不可公开读取，发布 token、DTO 脱敏、撤销、重新发布和旧 token 失效。
- 远程头像默认关闭；HTTPS/域名/端口校验；IPv4/IPv6 私网、元数据、重定向、超大内容、伪图片；TLS 连接固定到已校验 IP。
- 小程序自动注入 Bearer、Public 匿名、401 清缓存、GET 最多重试一次、写请求不重试、退出先清本地、启动时清理过期会话缓存。
- 显式迁移不会由基础建表自动代替，且可重复、可回退、可再次升级。

## 仍需人工验证

1. 在微信开发者工具和两台真机上完成登录、过期重登、退出和 A/B 账号切换，确认页面内存态也无旧报告、地址或订单闪现。
2. 在测试环境配置真实微信 AppID/Secret，确认 code 交换成功；若使用 CloudBase 身份头，先验证所有直连入口已隔离再单独评审开关。
3. 在隔离 MySQL 8 测试库执行迁移 upgrade/重复 upgrade/downgrade/upgrade，不得复用生产数据卷。
4. 开启公共分享前在测试环境验证微信会话分享、时间线打开、撤销后已发消息失效和脱敏 DTO。
5. 使用真实 COS 测试客户端头像直传；远程抓取开关继续保持关闭。
6. 对小屏、安卓、后台恢复和网络中断做现有报告/依据页回归；本阶段未改 UI 结构。

## 回滚

1. 保持 `COMMERCE_CHECKOUT_ENABLED`、`DIY_PUBLIC_SHARE_ENABLED`、`REMOTE_AVATAR_FETCH_ENABLED`、`LOGISTICS_SYNC_ENABLED`、`ALLOW_DEV_WECHAT_LOGIN` 和 `TRUST_CLOUDBASE_IDENTITY_HEADERS` 为 `false`。
2. 回退应用代码；优先保留新增表和字段，它们对旧版本为扩展性结构。
3. 只有确认没有新版本实例且允许所有新会话和分享状态失效时，按 `03-p0a-migration-runbook.md` 执行 downgrade。
4. 清理小程序本地 Token 和私有缓存，要求用户重新登录。

## 上线判断

P0-A 子阶段的代码和自动化验证达到验收条件，但 MySQL 隔离环境、微信/COS 真机链路仍需人工验证，且订单定价、库存、支付、退款和物流等后续阻断项不属于本阶段。因此项目整体判断保持 **NO-GO**。
