# 最终测试审计

## 结论

定向安全/交易/报告/运行时测试和小程序 JS 测试通过，但完整后端有 1 个真实失败，4 组 MySQL 门禁被跳过。测试结论为 **FAIL / NO-GO**。

## 实际执行命令与结果

| 命令 | 结果 |
| --- | --- |
| `PYTHONPATH=. /tmp/yujian-p1d-venv/bin/python -m pytest -q --ignore=tests/minium` | **FAIL**：204 passed, 4 skipped, 1 failed, 1 warning |
| 定向 P0-A/P0-B/P1-A/P1-B/P1-C/P1-D 安全、交易、报告、运行时测试 | **PASS**：108 passed, 1 warning |
| `npm run build:check` | **PASS**：环境隔离检查通过，44 个 JS 文件语法通过 |
| `npm test` | **PASS**：48 个 JS 测试通过 |
| `npm audit --omit=dev --audit-level=high` | **PASS**：0 vulnerabilities |
| `.venv_codex/bin/python scripts/check_migrations.py --backend sqlite` | **PASS**：SQLite migration round trip 通过 |
| `scripts/check_toolchain.py`、`scripts/check_repository.py`、`scripts/scan_secrets.py` | **PASS** |
| `pip-audit -r requirements.lock` | **PASS**：未发现已知生产依赖漏洞 |
| Python `compileall`、release shell `bash -n` | **PASS** |
| `git diff --check` | **PASS** |

## 新增/当前失败

`tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements` 失败：财富愿望的主石实际返回 `green_phantom`，不在测试定义的财富主石集合中。该失败影响核心推荐结果，属于 P1，不能以“既有失败”豁免。

## 跳过与未执行

- 4 个 skip 分别对应 P0-B、P1-A、P1-B、P1-C 的 MySQL gate。
- 本机没有 Docker、MySQL client、Nginx，因此没有执行 MySQL 并发、迁移/回退、备份恢复、镜像构建、切流和回滚演练。
- Minium 未运行，符合 `AGENTS.md` 默认规则，但不能作为 E2E 通过证据。
- 未调用真实微信支付、退款、物流或生产服务。

## 判定

SQLite 结果不能替代 MySQL 行锁与并发验证。完整后端失败和 MySQL 门禁缺失均阻止 GO。
