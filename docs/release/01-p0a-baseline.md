# P0-A 实施基线

记录时间：2026-07-12（修改前）

## Git 状态

- 分支：`codex/material-taxonomy-checkpoint`
- 最近提交：
  - `454668e feat: show MBTI influence in assessment results`
  - `01f6a31 fix: render recommended beads in workspace`
  - `1ed81a0 feat: refine bracelet interactions and assessment results`
  - `1a081f8 Improve recommendation and workspace flows`
  - `3d4ec9d Refine design preview layout and plan timestamps`
- 修改中的文件：`miniprogram/app.json`、测算页、隐私页、报告页、`miniprogram/utils/auth.js`、`tests/js/light-priority-ux.test.js`。
- 未跟踪内容：`miniprogram/pages/report-basis/`、`specs/`。
- P0-A 必须保留上述已有修改，不得回退或覆盖。

## 修改前验证结果

### 后端普通测试

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv_codex/bin/python -m pytest -q --ignore=tests/minium -p no:cacheprovider
```

结果：`92 passed, 1 failed, 1 warning`。

修改前已存在的失败：

```text
tests/test_energy.py::test_recommendation_primary_follows_wish_and_support_avoids_primary_elements
expected one of titanium_quartz/citrine/gold_rutilated_quartz/sunstone,
actual green_phantom
```

该失败属于既有推荐规则问题，不归因于 P0-A。

### 小程序 JS 测试

命令：

```bash
node --test tests/js/*.test.js
```

结果：`31 passed, 0 failed`。

### 差异检查

命令：

```bash
git diff --check
```

结果：通过，无空白错误。

### 未执行

- Minium：按项目默认规则跳过。
- MySQL 集成测试：基线阶段未启动本地 Docker。
- 生产数据库、生产部署、真实支付、退款和物流：均未连接或调用。
