# CI 质量门禁

代码托管为 GitHub，因此使用 `.github/workflows/ci.yml`。工作流固定第三方 Action commit，不使用 `continue-on-error`，任一步退出非零即阻止合并和候选镜像构建。

## Quality job

- Python `3.12.13`、Node `24.17.0`、npm `11.13.0`。
- `requirements-dev.lock` 使用 hash 校验安装，Node 使用 `npm ci`。
- 工具链、依赖固定、文件大小、构建产物、Secret 和 `git diff --check`。
- Python compileall、小程序 JS 语法、环境隔离、JS 单测和后端全量 pytest，默认跳过 Minium。
- SQLite migration upgrade/downgrade/upgrade。

## Security job

- Secret、依赖固定和仓库构建产物检查。
- `pip-audit` 和 `npm audit`；即使业务测试失败也会独立执行并给出证据。

## Container job

- `compose.yaml` 与 `compose.release.yaml` 官方解析。
- 使用摘要基础镜像和 hash lock 执行 clean Docker build。

## MySQL job

CI 使用摘要固定的临时 MySQL，创建 P0-B、P1-A、P1-B、P1-C、P1-D 独立数据库。依次执行并发库存、支付事件、报告幂等、物流租约、迁移往返和备份恢复。SQLite 结果不能替代此 job。

## 候选镜像

`release-candidate.yml` 只允许手动触发，必须先找到当前 commit 成功的 `ci.yml` 运行，随后推送唯一版本 tag。它只构建并上传镜像，不连接服务器、不迁移数据库、不自动部署。

## 失败策略

测试、构建、漏洞、Secret、migration、MySQL、备份恢复或 Docker 任一失败均为 NO-GO。测试不得改为 skip；隔离 MySQL job 不得用共享生产库。
