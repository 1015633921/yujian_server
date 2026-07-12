# P1-B API 契约

所有报告接口使用 User Bearer，并从 `current_user` 判定所有权；客户端 `user_id` 不是授权凭据。资源不存在或不属于当前用户统一返回不泄露存在性的 404。V2 Flag 关闭时 V2 读取接口返回 503。

## 生成报告

`POST /api/v1/assessment/energy`，V2 开启时必须带 `Idempotency-Key`。响应至少包含 assessment/report ID、report version、服务端创建时间、算法/Schema/校准版本、校准状态和不可变报告投影。客户端不能提交 `report_version`，额外字段由 Schema 拒绝。

## 读取接口

- `GET /api/v1/reports/{report_id}?report_version=N`：不含输入快照的报告详情。
- `GET /api/v1/reports/{report_id}/basis?report_version=N`：仅所有者可见的输入快照、校准状态和依据派生信息。
- `GET /api/v1/reports/{report_id}/poster?report_version=N`：专用脱敏 DTO，带 `sanitized_payload_hash`。
- `POST /api/v1/reports/{report_id}/diy-recommendation`：请求含 `report_id`、`expected_report_version`、腕围和珠径；响应及 workbench payload 保存来源版本。

报告 ID 正确但版本不匹配统一返回 HTTP 409：

```json
{"detail":{"code":"report_version_conflict","message":"报告版本不匹配，请重新加载指定报告"}}
```

同一幂等键绑定不同规范化输入返回 409 `report_idempotency_conflict`。数据库异常原文不返回客户端。

## 海报隐私

海报 DTO 只含报告标识、创建时间、核心结论、风格建议、调节策略、元素展示值、均衡度、关键词和品牌字段。默认不含出生日期/时间、校准前后时间、地点、排盘、MBTI、状态、直觉色彩、user ID、OpenID 或手机号。Canvas 只接收该 DTO 的展示投影，临时图片记录 report ID、version 与 payload hash。
