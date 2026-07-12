# P1-B 迁移与回滚手册

迁移版本：`20260712_04_p1b_report_snapshots`。变更是 additive/expand-first：新增三张表，并仅向 `assessment_recommendations` 增加可空 `report_id`、`report_version` 和查询索引。没有删除或重命名旧字段，应用启动不会创建这些 P1-B 结构。

## 表与约束

- `report_snapshots`：主键 report ID；assessment 唯一；`(user_id, report_version)` 唯一；用户/时间和输入摘要索引。
- `report_generation_requests`：`(user_id, idempotency_key)` 唯一；报告和状态索引。
- `report_version_counters`：每用户一个带行锁的版本计数器。

## 共享测试库升级门禁

本项目按约定只使用长期测试库 `yujian_test`，禁止连接 `yujian`。迁移或 downgrade 前必须按 `08-shared-mysql-gate-runbook.md` 停止测试 API 并做可恢复的整库备份；仅备份几张表不足以恢复 DDL。

1. 记录备份 ID、Git HEAD、`schema_migrations` 和相关表行数。
2. 保持 `REPORT_VERSIONING_V2_ENABLED=false`。
3. 执行 `python -m app.migrations.runner upgrade --backend mysql`。
4. 检查重复 report ID、重复用户版本、空快照、不可解析 JSON 和 legacy 行数。
5. 运行 `tests/test_p1b_mysql_reports.py`，验证单步回退/升级和 10 worker 同键幂等。
6. 无论结果如何都恢复整库备份，重启测试 API 并做健康检查。

建议校验 SQL：

```sql
SELECT COUNT(*) FROM report_snapshots;
SELECT report_id, COUNT(*) c FROM report_snapshots GROUP BY report_id HAVING c > 1;
SELECT user_id, report_version, COUNT(*) c FROM report_snapshots GROUP BY user_id, report_version HAVING c > 1;
SELECT COUNT(*) FROM report_snapshots WHERE input_snapshot_json IS NULL OR output_snapshot_json IS NULL;
SELECT COUNT(*) FROM energy_assessments e LEFT JOIN report_snapshots r ON r.assessment_id=e.assessment_id WHERE r.report_id IS NULL;
```

## 历史回填

旧业务结果不重算、不重写。稳定 ID 由 assessment ID 的 SHA-256 生成；版本按用户、创建时间、assessment ID 的固定顺序分配；校准与算法元数据标为 `legacy_unknown`。大数据量上线前应在备份副本测量回填时长和 DDL 锁影响，必要时将回填拆为受控批处理后再放量。

## 应用回退

首选保持 Flag 关闭并回退应用，新表/可空列可保留，旧应用仍可启动。只有停止所有 V2 实例、确认无需保留 V2 数据并已有整库备份时，才执行单步 downgrade。MySQL DDL 会自动提交，不能把多条 ALTER 当成原子事务；失败时按备份恢复，而不是继续手工猜测 Schema。
