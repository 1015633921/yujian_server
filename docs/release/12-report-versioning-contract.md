# 报告版本契约

- `assessment_id`：一次已校验输入提交对应的内部测算记录 ID，不是用户、报告版本、分享或推荐 ID。
- `report_id`：不可预测的 `rpt_` 随机 ID，唯一标识一份不可变报告快照，不复用、不覆盖。
- `report_version`：当前用户报告演进序列中的正整数。相同幂等请求保持同一版本；用户主动重新分析产生下一版本。旧版本不会被最新版本替换。
- `algorithm_version`：服务端使用的测算/展示规则版本；历史快照固定。
- `schema_version`：输出快照结构版本。
- `calibration_version`：地点解析和真太阳时规则版本。
- `created_at`：服务端以 `Asia/Shanghai` 时区生成的 ISO 8601 时间。
- `source_input_hash`：规范化有效输入的 SHA-256；不记录到日志，也不替代所有权校验。

## 幂等规则

唯一范围为 `(user_id, idempotency_key)`。同键同规范化输入返回同一 assessment/report/version，且重试不重新运行算法；同键不同输入返回 409 `report_idempotency_conflict`。请求记录、版本计数、旧兼容 assessment 和报告快照在同一事务中提交。处理中事务失败会整体回滚，原键可重试。

## 快照边界

`input_snapshot_json` 只保存实际参与生成的规范化输入，属于私有数据；`output_snapshot_json` 保存原始元素、统一展示投影、结论、风格、调节策略和算法派生结果。普通 API 没有更新快照的能力。报告详情、依据、海报和推荐均读取该快照，不读取用户当前资料或重新执行测算。

历史 assessment 使用稳定 `legacy_<sha256(assessment_id)>` ID，按 `(user_id, created_at, assessment_id)` 分配可重复版本；不可恢复的元数据标记 `legacy_unknown`，不伪造地点校准状态。
