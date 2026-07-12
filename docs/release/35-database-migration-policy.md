# 数据库迁移策略

## 原则

迁移只通过 `python -m app.migrations.runner` 显式执行，应用启动不得自动运行生产 DDL。默认采用 expand/contract：先添加兼容字段或表，应用双读/双写或回填，稳定后在独立版本删除旧结构。

`schema_migrations` 记录版本、时间、操作者和 release；`schema_migration_history` 追加 upgrade/downgrade 事件。运行前必须设置 `MIGRATION_OPERATOR` 和 `RELEASE_VERSION`。

## 发布前

1. 生成带 checksum 的全库备份。
2. 在隔离恢复库验证 checksum、gzip 和实际 restore。
3. 在同版本 MySQL 的隔离副本执行 upgrade、downgrade、upgrade。
4. 评估 DDL 算法、锁时间、表大小、回填批次和维护窗口。
5. 确认旧应用可读取 expand 后结构，失败则 NO-GO。

`scripts/check_migrations.py --backend mysql` 只接受数据库名含 `test` 或 `ci`，会执行完整往返，绝不能指向生产。生产执行 upgrade 前再次确认备份 ID、checksum、操作者和版本；发布脚本不会偷偷迁移。

## 回滚

优先应用回滚并保留 additive schema。只有 migration 文档明确可逆、没有新格式数据、所有新进程已停止且已有新备份时才 downgrade。不可逆 DDL 或数据变换必须通过 forward fix 或备份恢复处理。
