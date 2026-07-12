# 依赖与工具链策略

## 固定版本

- Python：`3.12.13`，记录于 `.python-version`。
- Node：`24.17.0`，记录于 `.nvmrc`。
- npm：`11.13.0`，记录于 `miniprogram/package.json`。
- Python 基础镜像：`python:3.12.13-slim-bookworm@sha256:8a7e...f48b`。
- MySQL：`mysql:8.0@sha256:7dcd...ae2b`。

`requirements.txt` 和 `requirements-dev.txt` 只允许 `==`。完整传递依赖及发行包 hash 分别在 `requirements.lock` 和 `requirements-dev.lock`；生产镜像执行 `pip install --require-hashes`。小程序即使暂时无第三方包，也必须保留 `package-lock.json` 并使用 `npm ci`。

## 更新流程

1. 在专门 PR 修改直接依赖精确版本。
2. 用固定的 uv 命令重新生成 universal、hash lock。
3. 运行 clean install、全量测试、漏洞扫描和 Docker build。
4. 审核 changelog、许可证和小程序兼容性后合并。

禁止在 Dockerfile、CI 或服务器执行无版本的 `pip install xxx`、`npm install xxx`。`scripts/check_toolchain.py` 和 `scripts/check_repository.py` 负责 fail closed。
