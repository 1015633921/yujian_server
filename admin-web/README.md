# 宇涧运营后台 V2

这是与旧版 `static/admin` 并行建设的 Vue 3 运营后台。当前已完成基础框架和“人工搭配服务单列表”，旧 `/admin` 在全量验收前保持可用。

## 本地运行

先启动 FastAPI（默认 `http://127.0.0.1:8000`），再运行：

```bash
cd admin-web
npm install
npm run dev
```

需要连接其他后端时：

```bash
ADMIN_API_PROXY=https://api.yustream.cn npm run dev
```

开发地址默认为 `http://127.0.0.1:5174`。

## 验证命令

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

## 当前边界

- API：继续使用现有 `/api/v1/admin/*`，不复制业务逻辑。
- 鉴权：兼容旧后台的 `adminToken:test` / `adminToken:prod`。
- 路由：本地根路径开发，部署后目标路径为 `/admin-v2/*`。
- 构建：当前只输出 `dist/`，尚未接入 FastAPI 和 Docker；接入前不会影响现网 `/admin`。
- 数据：只连接真实接口，不在页面放置伪造经营数据。
- 人工搭配：`/design-requests` 使用轻量分页接口；详情页迁移完成前，列表操作会带服务单 ID 深链到旧后台继续处理。

完整迁移顺序见 `docs/refactor/admin-web-migration-plan.md`。
