# P0-A/P0-B API 访问矩阵

扫描日期：2026-07-12。`User Bearer` 指 `Authorization: Bearer <opaque token>`；当前用户始终由服务端会话推导。小程序 API 使用 Bearer，不使用 Cookie，因此 CSRF 不适用。测试主文件为 `tests/test_api.py`、`tests/test_p0a_security.py`；管理员接口沿用 `tests/test_api.py` 的管理员覆盖。

## Public 与 Webhook

| Method | Path | 当前/目标认证 | 分类 | Owner | user_id | IDOR | CSRF | 幂等要求 | 测试 |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | 冒烟 |
| GET | `/health` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | 冒烟 |
| GET | `/health/live` | 无 / 无 | Public liveness | 无 | 否 | 无 | N/A | 是 | `test_p1c_runtime.py` |
| GET | `/health/ready` | 无 / 无 | Public readiness | 无 | 否 | 无 | N/A | 是 | `test_p1c_runtime.py` |
| GET | `/internal/metrics` | 默认关闭；Bearer 运维令牌 | Internal | 无 | 否 | 无 | N/A | 是 | `test_p1c_runtime.py` |
| GET | `/admin` | 无 / 无 | Public 静态入口 | 无 | 否 | 无 | N/A | 是 | 手工 |
| GET | `/api/v1/assessment/options` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/crystals/catalog` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/materials` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/content-blocks` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/home-banners` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/community-posts` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/community-posts/{post_id}` | 无 / 无 | Public | 已发布内容 | 否 | 发布态校验 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/community/readiness` | 无 / 无 | Public readiness | 无 | 否 | 无 | N/A | 是 | `test_community_ugc.py` |
| GET | `/api/v1/community/posts[/{post_id}]` | 默认关闭；无 / 无 | Public UGC | 已发布内容 | 否 | 发布态校验 | N/A | 是 | `test_community_ugc.py` |
| GET | `/api/v1/community/posts/{post_id}/comments` | 默认关闭；无 / 无 | Public UGC | 已发布帖子与有效评论 | 否 | 发布态校验 | N/A | 是 | `test_community_ugc.py` |
| GET | `/api/v1/recommendation-plans` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/recommendation-plans/{plan_id}` | 无 / 无 | Public | 已发布内容 | 否 | 发布态校验 | N/A | 是 | `test_api.py` |
| POST | `/api/v1/auth/wechat-login` | 微信 code/header / 微信身份交换后创建会话 | Public 登录 | 微信主体 | 否 | 无 | N/A | 否 | `test_p0a_security.py` |
| GET | `/api/v1/diy-designs/shared/{share_token}` | 普通 design_id / 发布态+随机 token hash | Public（开关关闭） | 已发布分享 | 否 | 已修复 | N/A | 是 | `test_api.py` |
| GET | `/api/v1/daily-energy/options` | 无 / 无 | Public | 无 | 否 | 无 | N/A | 是 | `test_api.py` |
| POST | `/api/v1/wechat-pay/notify` | 微信签名 / 微信签名 | Webhook | 交易单 | 否 | 非用户接口 | N/A | 必须 | 支付测试 |
| POST | `/api/v1/wechat-pay/refund-notify` | 微信签名 / 微信签名 | Webhook | 退款单 | 否 | 非用户接口 | N/A | 必须 | 退款测试 |

## User Private

以下接口修改前均信任客户端 `user_id` 或可按资源 ID 直接访问；目标和当前实现均为 User Bearer。保留的 `user_id` 必须等于会话用户，否则 403；资源 ID 不属于当前用户时返回不泄露存在性的 404。

| Method | Path | Owner | user_id 位置 | 原 IDOR | 幂等/重试 | 测试 |
|---|---|---|---|---|---|---|
| POST | `/api/v1/auth/logout` | session.user | 无 | 否 | 幂等撤销；不自动重试 | `test_p0a_security.py` |
| GET | `/api/v1/auth/profile` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| POST | `/api/v1/auth/avatar` | session.user | form 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/auth/avatar-base64` | session.user | body 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/auth/profile` | session.user | body 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/auth/phone` | session.user | body 校验 | 是 | 不自动重试 | `test_api.py` |
| GET/POST/DELETE | `/api/v1/community-favorites[/{post_id}]` | session.user | query/body 校验 | 是 | GET 可重试；写不重试 | `test_p0a_security.py` |
| GET/POST/PATCH/DELETE | `/api/v1/community/me/posts`, `/api/v1/community/posts[/{post_id}]` | session.user / post.owner | 不接收 | 新增接口 | owner CRUD；草稿/待审/发布状态机 | `test_community_ugc.py` |
| POST | `/api/v1/community/posts/{post_id}/submit`, `/withdraw` | post.owner | 不接收 | 新增接口 | `pending` 重复提交和草稿重复撤回返回 `changed=false`；关闭审核时直接发布的重复提交也幂等；其余状态冲突返回 409 | `test_community_ugc.py` |
| PUT/DELETE | `/api/v1/community/posts/{post_id}/like`, `/save` | session.user | 不接收 | 新增接口 | 唯一键保证幂等 | `test_community_ugc.py` |
| POST/DELETE | `/api/v1/community/posts/{post_id}/comments`, `/api/v1/community/comments/{comment_id}` | session.user / comment.author | 不接收 | 新增接口 | 一级评论；作者软删除 | `test_community_ugc.py` |
| PUT/DELETE | `/api/v1/community/users/{user_id}/follow` | session.user | 不接收 | 新增接口 | 唯一键保证幂等；禁止关注自己 | `test_community_ugc.py` |
| POST | `/api/v1/community/reports` | session.user | 不接收 | 新增接口 | reporter + target 唯一去重 | `test_community_ugc.py` |
| POST | `/api/v1/diy-designs` | session.user | body 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/diy-designs/preview` | session.user | form 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| GET | `/api/v1/diy-designs` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| POST/DELETE | `/api/v1/diy-designs/{design_id}/share` | design.user | 无 | 是 | 每次发布新 token；写不重试 | `test_api.py` |
| GET/DELETE | `/api/v1/diy-designs/{design_id}` | design.user | query 可选校验 | 是 | GET 可重试；删除不重试 | `test_p0a_security.py` |
| GET/DELETE | `/api/v1/cart` | session.user | query 可选校验 | 是 | GET 可重试；删除不重试 | `test_p0a_security.py` |
| POST | `/api/v1/cart/items` | session.user | body 校验 | 是 | 业务 idempotency_key；不自动重试 | `test_api.py` |
| PATCH/DELETE | `/api/v1/cart/items/{cart_item_id}` | cart.user | body/query 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| GET/POST | `/api/v1/user/addresses` | session.user | query/body 校验 | 是 | GET 可重试；写不重试 | `test_p0a_security.py` |
| PUT/DELETE | `/api/v1/user/addresses/{address_id}` | address.user | body/query 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/user/addresses/{address_id}/default` | address.user | body 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| GET | `/api/v1/coupons/my` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_api.py` |
| GET | `/api/v1/coupons/available` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_api.py` |
| POST | `/api/v1/orders` | session.user | body 校验 | 是 | 必须 `Idempotency-Key`；仅网络超时复用同键重试一次；开关关闭 | `test_p0b_order_integrity.py`、`p0b-checkout.test.js` |
| GET | `/api/v1/orders` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| GET | `/api/v1/orders/{order_id}` | order.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| GET | `/api/v1/orders/{order_id}/payment-status` | order.user | 无 | 是 | 有限轮询；仅返回最小支付状态 | `test_p1a_payment_webhooks.py` |
| POST | `/api/v1/orders/{order_id}/pay` | order.user | body 校验 | 是 | 不自动重试；开关关闭 | `test_p0a_security.py` |
| POST | `/api/v1/orders/{order_id}/mock-pay` | order.user | body 校验 | 是 | 不自动重试；仅调试 | `test_api.py` |
| POST | `/api/v1/orders/{order_id}/mock-ship` | order.user | body 校验 | 是 | 不自动重试；仅调试 | `test_api.py` |
| POST | `/api/v1/orders/{order_id}/confirm-receipt` | order.user | body 校验 | 是 | 状态机幂等；不自动重试 | `test_api.py` |
| POST | `/api/v1/orders/{order_id}/cancel` | order.user | body 校验 | 是 | 状态机幂等；不自动重试 | `test_api.py` |
| PUT | `/api/v1/orders/{order_id}/receiver` | order.user | body 校验 | 是 | 不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/orders/{order_id}/after-sale` | order.user | body 校验 | 是 | 业务幂等；不自动重试 | `test_p0a_security.py` |
| POST | `/api/v1/orders/{order_id}/refund` | order.user | body 校验 | 是 | 必须业务幂等；不自动重试 | `test_p0a_security.py` |
| GET | `/api/v1/orders/{order_id}/logistics` | order.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| POST | `/api/v1/assessment/calculate` | session.user | body 可选校验 | 是 | 指纹缓存；写请求不自动重试 | `test_api.py` |
| POST | `/api/v1/assessment/energy` | session.user | body 可选校验 | 是 | V2 开启时必须 `Idempotency-Key`；网络超时复用原键一次 | `test_api.py`、`test_p1b_reports.py` |
| GET | `/api/v1/reports/{report_id}` | report.user | 无 | 是 | 明确 `report_version`；GET 可受控重试 | `test_p1b_reports.py` |
| GET | `/api/v1/reports/{report_id}/basis` | report.user | 无 | 是 | 明确版本；只返回所有者的输入快照 | `test_p1b_reports.py` |
| GET | `/api/v1/reports/{report_id}/poster` | report.user | 无 | 是 | 明确版本；返回专用脱敏 DTO | `test_p1b_reports.py` |
| POST | `/api/v1/reports/{report_id}/diy-recommendation` | report.user | 无 | 是 | `expected_report_version` 冲突返回 409 | `test_p1b_reports.py` |
| POST | `/api/v1/assessment/{assessment_id}/diy-recommendation` | assessment.user | 无 | 是 | 版本缓存；写请求不自动重试 | `test_p0a_security.py` |
| POST | `/api/crystal/assessment/` | session.user | body 可选校验 | 是 | 兼容路径；不自动重试 | `test_api.py` |
| GET | `/api/v1/assessment/history` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| GET | `/api/v1/privacy/data-summary` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_api.py` |
| DELETE | `/api/v1/privacy/personalization-data` | session.user | query 可选校验 | 是 | 幂等删除；不自动重试 | `test_api.py` |
| GET | `/api/v1/assessment/{assessment_id}` | assessment.user | 无 | 是 | GET 可受控重试一次 | `test_p0a_security.py` |
| GET | `/api/v1/daily-energy/today` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_api.py` |
| POST | `/api/v1/daily-energy/check-in` | session.user | body 校验 | 是 | 日期 upsert；不自动重试 | `test_api.py` |
| GET | `/api/v1/daily-energy/{energy_date}` | session.user | query 可选校验 | 是 | GET 可受控重试一次 | `test_api.py` |

## Admin

管理员 API 保留独立 Admin Bearer/角色权限，不使用普通用户会话。`/register` 和 `/login` 使用各自的引导密钥/凭据；CSRF 对 Bearer 不适用。下面每个路径均分类为 Admin，Owner 为后台角色或对应运营资源，客户端 `user_id` 不作为认证凭据。

| Method | Path | 权限/Owner | 幂等要求 |
|---|---|---|---|
| POST | `/api/v1/admin/register` | 引导注册策略 | 防重复注册 |
| POST | `/api/v1/admin/login` | 管理员凭据 | 登录限流（后续加固） |
| POST/GET | `/api/v1/admin/logout`, `/api/v1/admin/me` | 当前管理员会话 | 撤销幂等 / GET |
| GET/POST | `/api/v1/admin/admins` | 超级管理员 | 写操作防重复 |
| PUT/DELETE | `/api/v1/admin/admins/{admin_id}` | 超级管理员 | 状态更新幂等 |
| GET | `/api/v1/admin/login-logs`, `/api/v1/admin/dashboard`, `/api/v1/admin/system-status` | 管理员 | GET |
| POST | `/api/v1/admin/media/upload` | 运营角色 | 不自动重试 |
| GET | `/api/v1/admin/users`, `/api/v1/admin/users/{user_id}` | 客服/管理员 | GET |
| POST | `/api/v1/admin/users/avatar-sync` | 管理员 | 批次幂等要求 |
| GET | `/api/v1/admin/assessments`, `/api/v1/admin/daily-energies`, `/api/v1/admin/checkins` | 管理员 | GET |
| GET/PUT | `/api/v1/admin/daily-energy-rules` | 管理员 | PUT 幂等 |
| GET | `/api/v1/admin/orders`, `/api/v1/admin/orders/{order_id}` | 订单角色 | GET |
| POST | `/api/v1/admin/orders/{order_id}/ship` | 订单角色 | 必须状态机幂等 |
| GET/POST | `/api/v1/admin/wechat-trade/status`, `/api/v1/admin/wechat-trade/order-detail-path` | 超级管理员 | GET / 配置幂等 |
| POST | `/api/v1/admin/orders/{order_id}/sync-wechat-shipping` | 订单角色 | 第三方幂等 |
| POST | `/api/v1/admin/orders/{order_id}/status` | 订单角色 | 状态机幂等 |
| POST | `/api/v1/admin/orders/{order_id}/refund/approve` | 退款角色 | 必须幂等 |
| POST | `/api/v1/admin/orders/{order_id}/refund/reject` | 退款角色 | 状态机幂等 |
| POST | `/api/v1/admin/orders/{order_id}/refund/sync` | 退款角色 | 第三方幂等 |
| POST | `/api/v1/admin/orders/{order_id}/logistics/refresh` | 物流角色 | 任务幂等 |
| POST | `/api/v1/admin/orders/logistics/refresh-all` | 物流角色 | 批任务幂等 |
| POST | `/api/v1/admin/maintenance/inventory-reservations/release-expired` | 管理员 | 可重复执行；释放操作幂等 |
| GET | `/api/v1/admin/warehouse/overview`, `/api/v1/admin/warehouse/options`, `/api/v1/admin/warehouse/items`, `/api/v1/admin/warehouse/batches`, `/api/v1/admin/warehouse/movements` | 仓库角色 | GET |
| POST/PUT/DELETE | `/api/v1/admin/warehouse/items[/{item_id}]` | 仓库角色 | 写操作幂等键待 P1 |
| POST | `/api/v1/admin/warehouse/inbound`, `/api/v1/admin/warehouse/outbound` | 仓库角色 | 必须幂等 |
| POST | `/api/v1/admin/warehouse/suppliers`, `/api/v1/admin/warehouse/locations`, `/api/v1/admin/warehouse/channels` | 仓库角色 | upsert 幂等 |
| GET | `/api/v1/admin/materials`, `/api/v1/admin/material-spus`, `/api/v1/admin/material-options`, `/api/v1/admin/material-refs`, `/api/v1/admin/material-taxonomy`, `/api/v1/admin/material-option-items`, `/api/v1/admin/materials/audit-logs` | 材料运营角色 | GET |
| POST | `/api/v1/admin/material-taxonomy/categories`, `/api/v1/admin/material-taxonomy/series`, `/api/v1/admin/material-option-items`, `/api/v1/admin/materials`, `/api/v1/admin/materials/batch` | 材料运营角色 | 写操作按资源规则幂等 |
| PUT | `/api/v1/admin/materials/{material_id}` | 材料运营角色 | PUT 幂等 |
| DELETE | `/api/v1/admin/material-taxonomy/{item_id}`, `/api/v1/admin/material-option-items/{item_id}`, `/api/v1/admin/materials/{material_id}` | 材料运营角色 | 状态删除幂等 |
| GET/POST | `/api/v1/admin/home-banners` | 内容运营角色 | 写操作防重复 |
| PUT/DELETE | `/api/v1/admin/home-banners/{banner_id}` | 内容运营角色 | 状态更新幂等 |
| GET/POST | `/api/v1/admin/blocks` | 内容运营角色 | 写操作防重复 |
| PUT/DELETE | `/api/v1/admin/blocks/{block_id}` | 内容运营角色 | 状态更新幂等 |
| GET/POST | `/api/v1/admin/community-posts` | 内容运营角色 | 写操作防重复 |
| PUT/DELETE | `/api/v1/admin/community-posts/{post_id}` | 内容运营角色 | 状态更新幂等 |
| GET/POST | `/api/v1/admin/recommendation-plans` | 内容运营角色 | 写操作防重复 |
| PUT/DELETE | `/api/v1/admin/recommendation-plans/{plan_id}` | 内容运营角色 | 状态更新幂等 |

## 结论

P0-A 已移除用户私有接口对客户端 `user_id` 的信任。P0-B 已完成创建订单的服务端定价、幂等和库存预占。P1-A 增加支付/退款事件台账与服务端支付确认。P1-B 的报告、依据、海报和推荐接口均按当前用户与明确报告版本授权，但地点数据和 MySQL 门禁尚未完成；项目整体保持 NO-GO。
