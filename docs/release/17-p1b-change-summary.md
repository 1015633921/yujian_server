# P1-B 改造摘要

结论：**P1-B BLOCKED；项目整体 NO-GO。** 本地实现和 SQLite 自动化已完成，但全国地点数据与共享 MySQL 门禁未完成。

## 后端

- 新增 `app/reporting.py`：统一百分比、固定并列顺序、均衡度等级、报告展示投影和稳定输入摘要。
- 新增 `app/locations.py`：只收录项目原有 11 个坐标，未知地点不再回退 120°。
- 新增 `app/report_repository.py`：不可变快照、用户版本、事务幂等和 owner/version DTO。
- `service.py`、`api.py`、`schemas.py`、`energy.py`：生成/读取/依据/海报/推荐全链路绑定明确版本。
- `repository.py`：推荐来源版本、隐私摘要、删除和用户 ID 迁移覆盖报告表。
- `feature_flags.py`：`REPORT_VERSIONING_V2_ENABLED` 缺失时为 false。

## 前端

- `reportCache.js` 按 user + report ID + version 隔离缓存，登出和账号恢复时全部清除。
- `assessment.js` 每次主动生成创建新幂等键，网络超时重试复用原键。
- `report.js` 和 `report-basis.js` 使用明确版本；深链不替换为最新报告；依据输入按需读取且不持久缓存。
- 海报只使用脱敏 DTO，生成中固定原版本；报告切换后旧海报不能预览或保存。
- DIY 推荐传入并保存明确 report ID/version，不覆盖报告快照。

## 历史与兼容

迁移不改变旧结果；旧记录获得稳定 legacy ID、确定版本和 `legacy_unknown` 元数据。Flag 关闭时旧 API 行为保持兼容，V2 路由由服务端拒绝。没有 dual-read 字段拼接，也没有应用启动时 P1-B DDL。

## 未解决风险

1. 前端地点范围远大于 11 个可信坐标，完整地点库是 P1 阻塞。
2. P1-B MySQL migration/10-worker 幂等门禁尚未在已备份 `yujian_test` 执行。
3. 微信开发者工具和真机的断网重试、后台恢复、深链、旧报告、海报隐私及大字体仍需人工验证。
4. 既有财富愿望主石测试失败未在本阶段处理。
5. P1-C、P1-D 和重新全量上线审计仍未完成。

本阶段未连接生产数据库、未部署、未调用外部服务、未提交、未推送，三个高风险开关保持默认关闭。
