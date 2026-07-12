# P1-B 修改前基线

日期：2026-07-12。分支：`codex/material-taxonomy-checkpoint`；HEAD：`454668e`。

工作区在 P1-B 开始前已包含 P0-A、P0-B、P1-A 和报告 UI 的未提交修改。本阶段保留这些修改，没有执行 reset、checkout、commit 或 push。

| 检查 | 修改前结果 |
|---|---|
| `git diff --check` | PASS |
| 报告/测算定向测试 | `11 passed, 74 deselected, 1 failed` |
| P0-A 鉴权/迁移 | `17 passed` |
| 小程序 JS 测试 | `43 passed` |
| JS 语法检查 | 40 个文件通过 |
| 完整后端 | `158 passed, 2 skipped, 1 failed` |
| OpenAPI | 可生成；120 paths、48 schemas |
| 迁移 | P0-A、P0-B、P1-A，共 3 个版本 |

修改前唯一失败为 `tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements`：财富愿望期望指定主石集合，实际为 `green_phantom`。该失败早于 P1-B，且本阶段禁止修改测算算法。

修改前主要风险：`assessment_id` 同时承担报告定位；推荐会更新旧测算结果；报告、依据和海报依赖全局 `energyReport`；网络重试可能新建记录；未知地点静默使用东经 120°；百分比与排序在前端重复计算；海报没有服务端脱敏 DTO。
