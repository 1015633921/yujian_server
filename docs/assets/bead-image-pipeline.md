# 珠子图片素材处理管线

本文件约束“宇涧水晶”后续所有珠子实拍素材的处理方式。目标是让小程序商品卡片、DIY 工作台、购物车、确认订单和订单快照里使用同一套稳定、可验收的图片。

## 核心原则

- 原图、WPS 临时抠图结果、未验收图片，不能直接绑定数据库或上传给小程序使用。
- 对于实物照片，优先使用 WPS AI 抠图或同等质量的 AI 抠图工具，不再使用脚本自动猜圆裁剪作为最终素材。
- 当前推荐成品规格：`512 x 512`、白底、居中、WebP、单张小于 `200KB`。
- 分类、品种、材料编码必须经过人工确认表，不再完全依赖文件名自动推断。
- 没有用户明确命令时，只处理测试环境；正式环境上线前统一同步。
- 图片和音频资源默认上传腾讯云 COS/CDN，小程序包内不放大体积静态资源。

## 推荐工作流：WPS AI 抠图 + 白底

### 1. 生成分类确认表

```powershell
.\.venv_codex\Scripts\python.exe scripts\create_wps_bead_review_manifest.py
```

输出：

```text
outputs/wps-bead-review.csv
```

表格字段说明：

- `source_rel`：原图相对路径。
- `wps_expected_rel`：WPS 抠图结果建议保存路径。
- `suggested_category` / `suggested_series`：脚本根据目录和文件名给出的建议。
- `final_category` / `final_series`：人工确认后的最终分类和品种，以这两个字段为准。
- `material_code`：可选；如果为空，上传脚本会按最终品种推断。但重要品类建议手动填写固定 code。
- `approved`：填 `1`、`yes`、`approved`、`通过`、`保留` 均可被处理。
- `skip`：填 `1`、`yes`、`跳过` 时不会处理。

### 2. 使用 WPS AI 抠图

用 WPS 对原图进行 AI 抠图后，把结果按 `wps_expected_rel` 保存到：

```text
outputs/wps-bead-cutouts/
```

例如原图：

```text
水晶图片/粉水晶/IMG_0001.HEIC
```

建议 WPS 导出：

```text
outputs/wps-bead-cutouts/粉水晶/IMG_0001.png
```

WPS 输出透明底或白底都可以。后续脚本会统一转成白底 WebP。

### 3. 标准化为小程序图片

只处理确认表里 `approved` 的图片：

```powershell
.\.venv_codex\Scripts\python.exe scripts\process_wps_bead_cutouts.py --clean
```

如果只是临时试跑，可以允许未审批图片：

```powershell
.\.venv_codex\Scripts\python.exe scripts\process_wps_bead_cutouts.py --allow-unapproved --clean
```

输出：

```text
static/materials/beads/wps-white/<slug>/<slug>-NN.webp
outputs/wps-bead-white/<slug>/manifest.json
outputs/wps-bead-white/<slug>/_contact-sheet.jpg
outputs/wps-bead-white/_summary.json
```

### 4. 人工验收

必须查看每个 `_contact-sheet.jpg`。

重点检查：

- 珠子是否完整，没有被切边。
- 珠子是否居中。
- 白底是否干净。
- 是否混入手、盒子、手串成品、多个珠子、品类说明图。
- 分类和品种是否正确。
- 同一品种下图片风格是否一致。

差图直接在 WPS 输出目录或确认表中删除/标记 `skip`，然后重新跑标准化脚本。

### 5. 上传测试 COS 并绑定测试库

WPS 白底素材确认后，上传测试环境：

```powershell
.\.venv_codex\Scripts\python.exe scripts\upload_real_bead_photo_assets_to_cos_and_db.py `
  --app-env test `
  --mysql-database yujian_test `
  --assets-root static/materials/beads/wps-white `
  --manifest-root outputs/wps-bead-white `
  --cos-prefix materials/beads/wps-white `
  --bucket yujian-test-1258267288 `
  --cdn-base-url https://cdn-test.yustream.cn/
```

上传脚本会：

- 优先读取 manifest 中的 `final_category`、`final_series`、`material_code`。
- 同名品种更新图片池。
- 数据库没有对应品种时，创建 `8mm - 15mm` 的 SKU。
- 图片 URL 使用测试 CDN。

### 6. 验证

验证内容：

- 本地 WebP 是否都是 `512 x 512`。
- 单张是否小于 `200KB`。
- CDN URL 是否 `200 OK`。
- `/test-api/api/v1/materials` 是否返回新图片池。
- 小程序 DIY 工作台、购物车、确认订单、订单详情缩略图是否正常。

## 撤回测试环境错误图片

如果测试库已经绑定过错误图片，可以先 dry-run 查看影响：

```powershell
.\.venv_codex\Scripts\python.exe scripts\clear_real_photo_material_bindings.py
```

只禁用由脚本新建的 `real_*` 行：

```powershell
.\.venv_codex\Scripts\python.exe scripts\clear_real_photo_material_bindings.py --apply --mode disable-created
```

清空所有匹配图片字段风险较高，除非确定要临时让这些珠材无图：

```powershell
.\.venv_codex\Scripts\python.exe scripts\clear_real_photo_material_bindings.py --apply --mode clear-images
```

## 不同图片类型

- DIY/商品珠子素材：走本文档 WPS 白底管线。
- 商品详情大图：可以保留环境和手串整体氛围，但不要混入 DIY 珠子图片池。
- 首页 Banner、灵感图、报告海报：不走珠子裁剪管线，但仍需上传 COS/CDN。
