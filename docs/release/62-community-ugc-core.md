# 灵感社区 UGC 核心切片

## 范围与兼容性

- 现有官方编辑内容接口 `/api/v1/community-posts` 与表 `community_posts` 保持不变。
- 用户内容使用独立命名空间 `/api/v1/community/*` 和独立 `community_ugc_*` 表。
- 所有写操作从 `require_current_user` 的 Bearer 会话主体取得用户 ID；请求体不接受 `user_id`。
- 本切片不提供管理员审核接口，不接收媒体二进制，也不接受客户端外链图片。

## 功能开关

| 变量 | 默认 | 作用 |
|---|---:|---|
| `COMMUNITY_UGC_ENABLED` | `false` | 打开 UGC 读取接口，并使 UGC 表进入全局 readiness 必需表集合 |
| `COMMUNITY_UGC_WRITES_ENABLED` | `false` | 在读取开关开启后，允许用户写入 |
| `COMMUNITY_MODERATION_REQUIRED` | `true` | 提交后进入 `pending`；显式设为 `false` 时提交可直接进入 `published` |
| `COMMUNITY_READINESS_CACHE_TTL_SECONDS` | `5` | 进程内 schema readiness 缓存秒数，限制在 0.1–60 秒；迁移后可调用服务的 `clear_readiness_cache()` 主动失效 |

写开关开启、读开关关闭属于无效配置，`/health/ready` 会返回配置失败。
生产发布校验与启动校验额外强制 `COMMUNITY_UGC_WRITES_ENABLED=false` 且
`COMMUNITY_MODERATION_REQUIRED=true`；只有测试和开发环境可显式放开写入或关闭审核。
普通 UGC 接口和公共 readiness 路由共享短 TTL 单飞缓存，不会为每个请求扫描数据库。

## 保守状态规则

```text
draft --submit--> pending --trusted moderation adapter--> published
  ^                    |                              |
  +------withdraw------+------------withdraw----------+
```

- 默认必须审核；本切片刻意没有 HTTP 审核入口。
- 测试或已明确无需审核的环境可显式设置 `COMMUNITY_MODERATION_REQUIRED=false`，此时 `draft --submit--> published`。
- `pending` 重复提交返回 `changed=false`；仅在 `COMMUNITY_MODERATION_REQUIRED=false` 时，已直接发布的帖子重复提交也返回 `changed=false`。默认审核模式下，已发布帖子不能重新提交。
- 只有草稿可编辑。所有状态均可由所有者软删除；公开列表和详情只返回未删除的 `published`。
- `design_id` 必须属于当前用户；`source_post_id` 必须指向当前公开的 UGC 帖子。提交和可信审核发布时会在同一事务重新校验来源状态。
- 提交和可信审核发布也会重新锁定并校验 `design_id` 归属；DIY 方案删除会拒绝任何未删除 UGC 帖子的引用，避免发布内容悬空。
- PATCH 可显式传 `null` 清除 `design_id` / `source_post_id`；标题、正文、图片和标签不能传 `null`。
- 公开评论读取在同一事务校验帖子与读取评论；点赞、收藏、评论、举报和帖子状态变更在 MySQL 中锁定同一帖子行后串行执行。

## 生产写入硬阻塞

本切片只允许只读试运行。发布校验和启动校验会拒绝生产写开关；以下能力完成并通过滥用与并发验收前，生产环境必须保持 `COMMUNITY_UGC_WRITES_ENABLED=false`：

- 可操作、可审计的管理员审核入口与待审队列；
- 用户/IP 维度的限流、发布/评论/举报配额和异常行为处置；
- 媒体服务端上传、归属校验与内容审核；
- 审核失败、限流、配额耗尽等前端错误状态。
- 设计复制/公开链路对被删除、撤回及无权设计的完整错误处理。

`COMMUNITY_MODERATION_REQUIRED=false` 只用于隔离测试或已明确不需要审核的非生产环境，不能用来绕过上述生产门禁。

当前 schema readiness 校验迁移版本和 6 张表是否存在，不逐列比对字段和唯一约束。列/约束漂移深检需要额外的 SQLite `PRAGMA` / MySQL `INFORMATION_SCHEMA` 基线及双后端测试，后续应放在启动或显式 health 检查中，不能重新加入普通请求热路径。

## 迁移与回滚

迁移版本：`20260717_09_community_ugc_core`（`_08` 已由网页登录配对切片预留）。

```bash
python -m app.migrations.runner upgrade --backend sqlite
python -m app.migrations.runner downgrade --backend sqlite --steps 1
```

生产或共享 MySQL 必须遵循既有备份、操作者、发布版本和隔离测试门禁；不能直接使用上述 SQLite 示例替代生产变更流程。回滚只删除新建的 `community_ugc_*` 表，不触碰官方 `community_posts`。

## 后续边界

- 媒体上传需要服务端签发、对象归属绑定、类型/大小校验和内容审核后才能开放。
- 管理审核、限流/配额/反滥用、通知、二级回复、复制设计和公开 SEO 元数据不在本切片；其中审核与限流/配额是生产写开关的硬阻塞项。
- `design_id` 与 `source_post_id` 已预留并执行归属/可见性校验；未实现复制设计。
