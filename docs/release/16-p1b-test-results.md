# P1-B 验证结果

日期：2026-07-12。结论：**P1-B BLOCKED；项目整体 NO-GO。** 本地/SQLite 改造没有新增失败，但完成条件要求的可靠全国地点数据和共享 MySQL 迁移/并发门禁尚未具备。

## 验收表

| 检查项 | 结果 | 证据 | 剩余风险 |
|---|---|---|---|
| report ID/version 与不可变快照 | PASS（SQLite） | P1-B 定向 `22 passed`；GET 不重算、旧版本不变 | MySQL 未验收 |
| 生成幂等与事务回滚 | PASS（SQLite）/ BLOCKED（MySQL） | 同键重试、不同输入 409、2 worker、注入事务失败全回滚 | 10 worker MySQL 门禁未执行 |
| 报告/依据/海报/推荐一致性 | PASS | 四个 DTO 的 ID/version、元素与均衡度一致；错误版本 409 | 真机后台恢复仍需走查 |
| 鉴权与 IDOR | PASS | 用户 A 的报告、依据、海报和推荐均对用户 B 返回 404 | 部署层身份头配置仍需上线审计 |
| 海报隐私 | PASS（DTO/静态） | 自动断言不含生日、时间、地点、MBTI、状态、user/openid/phone | 真机生成图片需人工 OCR/目视复核 |
| 地点校准 | BLOCKED | 已支持城市 applied；未知/错误/时间未知不显示校准时间；无 120° 回退 | 只有 11 个可信城市，无法完成全国、同名城市抽样 |
| 百分比、并列与均衡度 | PASS | 最大余数法总计 100；99/101、2/3/5 项并列、0、极端分布通过 | 业务算法本身不在本阶段变更 |
| 前端缓存与账号切换 | PASS（自动化） | user + report ID + version；登出全清；深链不读全局旧报告 | 微信后台恢复和真机存储需人工验证 |
| SQLite 迁移往返 | PASS | legacy 稳定回填、重复 upgrade、downgrade、upgrade 通过 | 大表耗时和 MySQL DDL 锁未测 |
| Feature Flag | PASS | 三个高风险 Flag 缺失时均为 `False` | 生产配置仍需双人复核 |
| P0-A/P0-B/P1-A 回归 | PASS（本地） | 定向 `82 passed`；完整后端仅保留原失败 | 三阶段 MySQL 门禁均仍需共享库执行 |

## 执行命令与真实结果

| 命令 | 结果 |
|---|---|
| `pytest -q tests/test_p1b_reports.py tests/test_p1b_migrations.py` | `22 passed, 1 warning` |
| P1-B + P0-A/P0-B/P1-A 定向命令 | `82 passed, 1 warning`（补充 P1-B 边界测试前）；后续完整测试覆盖新增用例 |
| `pytest -q --ignore=tests/minium` | `180 passed, 3 skipped, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `47 passed, 0 failed` |
| 全部非 vendor 小程序 JS 执行 `node --check` | 40 个文件通过 |
| 全部 `app/**/*.py` 执行 `py_compile` | PASS |
| OpenAPI 生成 | PASS；124 paths、48 schemas；4 个 versioned report paths 存在 |
| SQLite P1-B upgrade/downgrade/legacy backfill | PASS，包含在迁移测试中 |
| `pytest -q tests/test_p1b_mysql_reports.py -m mysql_integration` | `1 skipped`，未显式开启门禁 |
| 指向 `yujian_test` 但不提供备份许可的安全负向测试 | 预期 FAIL：要求 `ALLOW_SHARED_MYSQL_TEST_DATABASE=1` 和备份 ID，未连接数据库 |
| 缺省 Feature Flag 探针 | report V2 / checkout / payment 均为 `False` |
| `git diff --check` | PASS |

三个 skipped 是 P0-B、P1-A、P1-B 的 MySQL 集成门禁，不能用 SQLite 结果替代。

## 失败分类

原有失败：`tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements`，期望财富愿望主石集合，实际返回 `green_phantom`。它在 P1-B 基线前已存在，本阶段未修改测试期望或测算算法。

新增失败：无。迁移开发中曾发现纯交易测试库缺少 `assessment_recommendations` 时 P1-B 迁移失败；已通过表存在性检查修复，P0-B/P1-A 定向回归随后通过。

## 人工/真机清单

1. iPhone 小屏、安卓窄屏和系统大字体。
2. 报告进入依据再返回，滚动位置和图表动画保持。
3. 创建新报告后通过深链查看旧报告；后台恢复不切换版本。
4. 账号切换与登出后报告、依据、海报、推荐均不串号。
5. 已支持地点、未知地点、错误代码和未知出生时间的不同文案。
6. 海报生成期间创建新报告，旧海报不能保存；图片中无个人输入。
7. 生成时断网重试和快速重复点击只产生一份报告。
8. Flag 开启/关闭的旧客户端兼容行为。

## 解阻条件

1. 获得合法、完整、版本化且带稳定行政区代码的地点数据并补齐全国/同名城市测试。
2. 按共享 MySQL 手册停止测试 API、整库备份 `yujian_test`，运行 P0-B/P1-A/P1-B 门禁，随后恢复备份并验证健康检查。
3. 完成微信开发者工具和真机清单，再运行全量审计。

本阶段未连接生产数据库、未部署、未调用真实微信或地理服务、未提交、未推送。
