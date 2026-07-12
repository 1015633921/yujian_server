# 报告生命周期图

## 修改前

| 步骤 | 前端/API/服务 | 数据与缓存 | 一致性风险 |
|---|---|---|---|
| 填写输入 | `assessment.js` | 表单、`assessmentDraft` | 地点只有名称，无稳定代码 |
| 生成画像 | `POST /assessment/energy` -> `AssessmentService.calculate_energy` | `energy_assessments` | 指纹缓存与强制重算混用；无请求幂等 |
| 地点校准 | `EnergyCalculator.calculate_true_solar_time` | 内置少量坐标 | 未命中使用 120°，仍显示已校准 |
| 报告页 | `report.js` | 全局 `energyReport` | 无用户/版本作用域，旧页可能读取最新报告 |
| 依据页 | `report-basis.js` | `reportBasisView` | 依据是页面派生副本，不是服务端快照 |
| 海报 | 前端 Canvas | 当前页面对象 | 无脱敏 API；生成中报告变化可能混版 |
| DIY 推荐 | `POST /assessment/{assessment_id}/diy-recommendation` | `assessment_recommendations` | 推荐会回写测算结果；可能读取变化后的结果 |
| 重试/后台恢复 | 请求封装与 `onShow` | 最后一份全局缓存 | 重复报告、账号串缓存、旧页被最新值替换 |

## 修改后

```text
规范化输入 + current_user + Idempotency-Key
  -> 显式地点解析/校准状态
  -> 单次算法执行
  -> 同一事务写 assessment + immutable report snapshot + idempotency record
  -> report_id/report_version
     -> 报告详情 DTO
     -> 私有依据 DTO
     -> 脱敏海报 DTO
     -> 绑定版本的 DIY 推荐
```

| 步骤 | API/存储 | report 语义 | 是否重算/读可变资料 |
|---|---|---|---|
| 生成 | `POST /assessment/energy` | 返回新 `report_id` 与用户序列 `report_version` | 首次执行算法；同键重试直接返回快照 |
| 持久化 | `report_snapshots`、`report_generation_requests`、`report_version_counters` | 输入、输出、算法和校准元数据不可变 | 同一事务，无中间完成窗口 |
| 报告 | `GET /reports/{id}?report_version=N` | 明确版本、所有者校验 | 不重算，不读当前资料 |
| 依据 | `GET /reports/{id}/basis` | 同一快照的私有输入 | 不持久化到前端依据缓存 |
| 海报 | `GET /reports/{id}/poster` | 同一快照的脱敏投影和 payload hash | 不含个人输入，不读最新报告 |
| 推荐 | `POST /reports/{id}/diy-recommendation` | 保存来源 ID/版本 | 只用快照；不更新报告 |
| 前端缓存 | `reportSnapshot:{user}:{id}:v{N}` | 用户、ID、版本三重作用域 | 深链只加载指定版本；登出全清 |
| 重新分析 | 新幂等键 | 新 report ID，版本递增 | 旧报告保持可读 |
| 后台恢复 | 页面保留 requested ref | 旧页不自动切换 active ref | 无混合字段 |

当前 V2 由服务端 Feature Flag 控制且默认关闭。旧客户端继续走旧流程，不与 V2 DTO 混合。
