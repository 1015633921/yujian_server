# P1-C 验证结果

日期：2026-07-12。结论：**P1-C BLOCKED；项目整体 NO-GO。** 本地实现和 SQLite 自动化没有新增失败，但生产数据库使用 MySQL，租约迁移与双 worker 条件更新尚未在已备份的 `yujian_test` 运行；本机也没有 Docker CLI，无法执行 `docker compose config` 的官方解析和容器启动验收。

| 检查项 | 结果 | 证据 | 剩余风险 |
|---|---|---|---|
| Web 无后台物流线程 | PASS | 静态断言 `main.py` 无 thread/loop；独立 worker 关闭时不创建 DB | 测试环境需确认多 Uvicorn worker 只处理 HTTP |
| 双 worker 单次执行 | PASS（SQLite）/ BLOCKED（MySQL） | 两 worker 并发仅一个 task run；另一实例 skipped_locked | MySQL 条件更新门禁未执行 |
| 失败重试和副作用 | PASS | 整批瞬时失败重试；只重试失败订单；最多 3 次 | 真实快递100错误分类需测试环境契约夹具 |
| request ID | PASS | 自动生成、自定义、重复复用、非法替换、异常响应和下游传递通过 | Nginx 透传需部署侧确认 |
| 结构化日志与脱敏 | PASS（单元/静态） | Token、OpenID、手机号、地址、用户 ID 均不出现在 JSON 日志 | Uvicorn/Nginx 集中日志格式属于 P1-D |
| 安全异常响应 | PASS | validation/HTTP/500 均含 request ID；500 不含异常、SQL、路径和手机号 | 各业务 4xx 文案仍需持续审查 |
| liveness/readiness | PASS | DB 正常、DB 缺失、配置错误、503 readiness、独立 liveness 覆盖 | MySQL 断连和恢复需容器环境演练 |
| 业务指标 | PASS（进程内） | 核心 counter、duration、error rate、登录成功/失败增量通过 | 多 worker 聚合和报警后端未建设 |
| 第三方超时 | PASS（自动化/静态） | 微信、快递、头像、COS 均有明确 timeout；快递 timeout 分类与 trace header 测试通过 | 未调用真实第三方 |
| P0-A 至 P1-B 回归 | PASS（本地） | 定向回归 `101 passed`；全量只有原有失败 | 既有 P0/P1 MySQL 门禁仍未完成 |
| 迁移往返 | PASS（SQLite）/ BLOCKED（MySQL） | v05 upgrade/downgrade/upgrade 通过 | MySQL DDL 与租约门禁待整库备份后执行 |

## 命令与真实结果

| 命令 | 结果 |
|---|---|
| `pytest -q tests/test_p1c_runtime.py` | `14 passed, 1 warning` |
| P1-C + P0-A/P0-B/P1-A/P1-B 定向回归 | `101 passed, 1 warning` |
| `pytest -q --ignore=tests/minium` | `194 passed, 4 skipped, 1 failed, 1 warning` |
| `node --test tests/js/*.test.js` | `48 passed, 0 failed` |
| 全部非 vendor 小程序 JS 执行 `node --check` | PASS |
| 全部 `app/**/*.py` 执行 `py_compile` | PASS |
| OpenAPI 生成 | PASS；126 paths、48 schemas，包含 live/ready |
| PyYAML 解析 `compose.yaml` | PASS；api、api-test、logistics-worker、mysql 四个 service |
| `docker compose config --quiet` | BLOCKED：本机没有 `docker` 命令 |
| 关闭物流开关执行 `python -m app.logistics_worker --once` | 退出码 0，未创建数据库文件 |
| P1-C MySQL test 默认执行 | `1 skipped` |
| 指向 `yujian_test` 但无备份许可的负向门禁 | 预期 FAIL，要求 `ALLOW_SHARED_MYSQL_TEST_DATABASE=1` 和备份 ID，未连接数据库 |
| 缺省物流/指标开关探针 | 均为 `False` |
| `git diff --check` | PASS |

完整后端唯一失败仍为 `tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements`：期望财富主石集合，实际 `green_phantom`。它在 P1-C 基线前已存在，本阶段没有修改测算算法或测试期望。

四个 skipped 是 P0-B、P1-A、P1-B、P1-C 的 MySQL 门禁，不能作为通过。P1-C 没有新增自动化失败。

## 环境验收清单

1. 整库备份 `yujian_test` 后运行四阶段 MySQL 门禁并恢复备份。
2. 启动两个 API worker 与两个 logistics worker，确认一个 task run。
3. 断开/恢复 MySQL，确认 readiness 503/200，liveness 始终 200。
4. 确认 Nginx 透传响应 `X-Request-ID`，日志不记录 Authorization。
5. 使用模拟快递服务验证 timeout、500、非法 JSON和连续失败告警。
6. 验证日志采集平台能按 request ID 串联 API 与独立 worker 事件。
7. 配置非公开 `LOG_HASH_SALT`；如开启指标端点，配置独立 Metrics token。

本阶段未连接生产、未部署、未调用真实物流/支付/COS、未提交、未推送。
