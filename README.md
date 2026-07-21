# 遇见水晶 DIY API

FastAPI 主服务用于专属水晶测算、五行能量画像与手串定制推荐。旧 Django 服务文件暂时保留，便于后续迁移其他业务接口。

## 启动 FastAPI

当前项目原有 `.venv` 已失效，请安装 Python 3.11+ 后重新创建：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如果需要运行测试或素材处理脚本，请安装开发依赖：

```powershell
pip install -r requirements-dev.txt
```

启动后访问：

- Swagger 接口文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 存活检查：`http://127.0.0.1:8000/health/live`
- 就绪检查：`http://127.0.0.1:8000/health/ready`

## 统一部署

测试和正式环境共用同一套 Docker 蓝绿发布命令，操作者只声明目标环境：

```bash
python scripts/deploy.py test
python scripts/deploy.py prod
```

镜像摘要和发布号由 CI 注入，运行配置来自部署机上的单一环境文件。发布过程自动完成
数据库备份、幂等迁移、候选健康检查、Nginx 原子切流和失败回滚。完整说明见
[`docs/deployment/docker-blue-green.md`](docs/deployment/docker-blue-green.md)。

## 运行进程与观测

FastAPI 进程只处理 HTTP，不再启动物流线程。物流同步必须作为独立进程运行：

```bash
LOGISTICS_SYNC_ENABLED=true python -m app.logistics_worker
```

多个物流进程通过 `runtime_task_leases` 数据库租约竞争，同一调度窗口只有一个执行者。
`LOGISTICS_SYNC_ENABLED` 默认 `false`；启用前必须执行 P1-C 迁移并通过 MySQL 租约门禁。

每个 HTTP 请求带 `X-Request-ID`，应用日志使用 JSON 格式且不记录 Token、OpenID、手机号、
地址或请求体。`/internal/metrics` 默认关闭；开启时还必须配置独立的
`METRICS_ACCESS_TOKEN`。详细运行策略见 `docs/release/20-runtime-current.md` 至
`docs/release/27-p1c-change-summary.md`。

## 专属水晶测算接口

### 获取测算页表单选项

```text
GET /api/v1/assessment/options
```

返回 16 种 MBTI、四种核心愿望、常用出生地坐标、腕围和珠径选项，可直接用于渲染小程序测算表单。

### 发起测算

```text
POST /api/v1/assessment/calculate
```

兼容旧地址：

```text
POST /api/crystal/assessment/
```

请求示例：

```json
{
  "user_id": "wx-openid-001",
  "name": "林安",
  "birthday": "1995-08-16",
  "birth_time": "09:30",
  "birth_place": "四川省成都市",
  "lng": 104.0665,
  "lat": 30.5723,
  "mbti": "INFJ",
  "core_wishes": [
    "健康护身/保持专注",
    "招财进宝/事业腾飞"
  ],
  "wrist_size_cm": 15.5,
  "bead_size_mm": 8,
  "force_recalculate": false
}
```

`mbti` 为可选字段；未填写时使用五行各 3 分的中性 MBTI 分布。`core_wishes`
允许选择 1 至 3 项，愿望模块总权重始终为 20 分，并在所有选中愿望涉及的五行间平均分配。
第一项愿望用于锁定 DIY 推荐的主石。小程序出生地使用地区选择组件，提交精确到市的名称。

响应中的关键界面字段：

| 字段 | 页面用途 |
| --- | --- |
| `solar_time` | 展示出生地与真太阳时校准结果 |
| `final_energy_profile` | 五行具体得分 |
| `energy_breakdown` | 八字、MBTI、姓名、愿望四项来源拆解 |
| `chart` | 雷达图 indicator、values 和颜色 |
| `interpretation` | 结果页标题、强弱项解读、平衡指数 |
| `primary_crystal` | 愿望优先的 C 位主石卡片 |
| `supporting_crystals` | 补足最低五行的配珠卡片 |
| `bracelet_plan.layout` | 按位置绘制手串预览 |
| `recommendation_copy` | 东方疗愈风定制推荐语 |
| `care_tips` | 佩戴与保养提示 |

相同输入默认读取 SQLite 中已有测算结果。需要重新计算时传：

```json
{
  "force_recalculate": true
}
```

## 推荐的小程序两阶段交互

第一步仅计算并展示能量画像，不要求用户填写腕围：

```text
POST /api/v1/assessment/energy
```

响应中的 `status` 为 `energy_ready`，`next_step` 会返回：

- 按钮文字：`生成我的专属手串`
- 操作类型：`open_wrist_size_form`
- 腕围和珠径表单配置
- 第二步提交接口地址

用户点击按钮、填写手腕周长后调用：

```text
POST /api/v1/assessment/{assessment_id}/diy-recommendation
```

请求示例：

```json
{
  "wrist_size_cm": 16.5,
  "bead_size_mm": 8
}
```

响应中的 `status` 变为 `diy_ready`，前端按照 `next_step.route` 跳转 DIY 工作台，并将
`workbench_payload` 作为工作台初始化数据。该数据已包含主石、配珠、每颗珠子的排列位置、
推荐文案、腕围和珠径，同时标记为可编辑。

### 报告版本 V2（默认关闭）

`REPORT_VERSIONING_V2_ENABLED` 缺失或为 `false` 时继续使用旧流程。开启前必须先执行
`20260712_04_p1b_report_snapshots` 迁移并通过 `docs/release/14-p1b-migration-runbook.md`
中的 MySQL 门禁。V2 要求生成报告时提供 `Idempotency-Key`，并以服务端返回的
`report_id + report_version` 读取报告、测算依据、脱敏海报数据和 DIY 推荐。

项目内地点数据目前只覆盖 11 个已有可信城市。未命中的地点不会再静默使用东经 120°，
而是返回 `unsupported` 并隐藏校准后时间。在获得合法、完整、版本化的地点数据前，不得
宣称支持全国地点校准，也不得在生产开启报告 V2。

### 测算历史与详情

```text
GET /api/v1/assessment/history?user_id=wx-openid-001&limit=20
GET /api/v1/assessment/{assessment_id}
GET /api/v1/crystals/catalog
```

## 算法结构

代码按业务步骤拆分：

- `app/schemas.py`：Pydantic 输入校验与响应模型
- `app/energy.py`：真太阳时、八字 Mock、MBTI、姓名、愿望四维融合
- `app/recommendation.py`：主石锁定、配珠补足、手串排布和推荐文案
- `app/repository.py`：SQLite 测算结果缓存与历史记录
- `app/service.py`：完整测算流程编排
- `app/api.py`：FastAPI 接口

五行总分严格为 100：

- 先天八字：55 分
- MBTI：15 分
- 姓名五行：10 分
- 当前愿望：20 分，对愿望对应的两个五行各加 10 分

当前八字计算使用可复现的 Mock 分布，并已预留 `calculate_bazi_mock` 替换点。接入正式八字库时，只需要让新实现继续返回总分为 55 的五行字典。

## 测试

```powershell
pip install -r requirements-dev.txt
pytest -q
```

覆盖内容：

- 四项权重与最终总分
- 成都经度真太阳时校准
- 主石严格遵循愿望池
- 配珠排除主石五行
- 页面所需雷达图与手串排布响应
- 非法 MBTI 参数校验

## 后续生产化建议

- 接入腾讯地图或高德地图地理编码，替换内置出生地坐标
- 接入正式八字历法库，替换 Mock 八字分布
- 将水晶图鉴迁移到商品数据库，并补充图片、SKU、库存和价格
- 继续轮换、审计服务端用户会话，并完善多设备会话管理
- 增加支付回调、库存锁定、内容审核与对象存储上传

## 用户会话与安全迁移

微信登录接口返回服务端 `access_token`、`expires_at` 和最小用户 DTO。所有用户私有接口要求：

```http
Authorization: Bearer <access_token>
```

请求中的 `user_id` 仅用于旧数据模型的一致性校验，不具有认证意义。数据库先执行显式安全迁移，应用启动不会自动创建会话表：

```bash
.venv_codex/bin/python -m app.migrations.runner upgrade --backend sqlite
```

完整安全迁移步骤见 `docs/release/03-p0a-migration-runbook.md`。订单完整性迁移与库存预占运维步骤见 `docs/release/05-p0b-migration-runbook.md`。支付事件迁移与补偿步骤见 `docs/release/06-p1a-migration-runbook.md`。结算、微信支付、公共 DIY 分享、远程头像抓取和物流同步默认关闭。

创建订单要求请求头 `Idempotency-Key`。订单金额只使用服务端 SKU 价格，以整数分保存在 `total_fee`；客户端价格仅用于发现展示价变化。库存预占默认 15 分钟过期，可通过 `INVENTORY_RESERVATION_TTL_SECONDS` 调整。过期释放由外部调度调用管理员维护接口，不在 Uvicorn worker 内启动线程。

## 临时公网测试

本地开发时可使用 Cloudflare Quick Tunnel 暴露 FastAPI：

```powershell
.\scripts\start_public_tunnel.ps1
```

脚本会输出一个临时 `https://*.trycloudflare.com` 地址。该地址在隧道进程退出或电脑重启后会变化，
需要同步更新 `miniprogram/utils/api.js` 中的 `DEFAULT_BASE_URL`。Quick Tunnel 仅用于测试，
无可用性保证；正式上线应使用固定 HTTPS 域名和已创建的命名隧道或云服务器。

## 每日能量补给站

首次登录、尚未完成专属测算的用户也可以直接获取每日内容：

```text
GET /api/v1/daily-energy/today
Authorization: Bearer <access_token>
```

首次用户返回 `mode: starter`，内容由以下部分构成：

- 通用当日五行：70%
- 当前用户 ID 与日期的稳定因子：20%
- 可选初始愿望：10%

同一用户同一天再次请求时直接读取数据库，返回 `cache_hit: true`，不会因刷新发生变化。

用户完成专属能量测算后，强制重算或次日生成的内容会自动切换为
`mode: personalized`，融合：

- 用户个人五行画像：40%
- 当日五行流转：35%
- 最近七天状态签到：25% 的动态影响

提交每日状态签到：

```text
POST /api/v1/daily-energy/check-in
```

```json
{
  "user_id": "wx-openid-001",
  "mood": 4,
  "sleep": 3,
  "stress": 2
}
```

查看指定日期或强制重新计算：

```text
GET /api/v1/daily-energy/2026-06-04
GET /api/v1/daily-energy/today?force_recalculate=true
```
