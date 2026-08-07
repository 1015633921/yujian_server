# 材料目录 V2

## 目标模型

材料目录只保留一条稳定层级：

```text
材料类型 material_types
  └─ 一级类目 material_categories_v2
      └─ 品种/系列 material_series_v2
          ├─ 系列资料 material_series_profiles_v2（1:1）
          ├─ 系列素材 material_series_assets_v2（1:N）
          └─ 具体 SKU material_skus_v2（1:N）
              └─ 库存 material_inventory_v2（1:1）
```

- 类型：珠子、配饰、吊坠等顶层业务形态。
- 一级类目：类型下用于运营筛选的稳定目录。
- 品种/系列：共享名称、材质编码、展示素材和推荐资料的 SPU。
- SKU：可定价、可售卖的具体规格；价格使用整数分，尺寸和重量保留输入精度。
- 库存：独立于商品资料，保存现存、占用和安全库存，是下单唯一库存账本。
- “冲突品种”不进入 V2；搭配规则只保留角色、推荐标签等有实际消费方的属性。

## 数据归属

| 数据 | 唯一归属 |
| --- | --- |
| 类型启用、排序 | `material_types` |
| 一级类目 | `material_categories_v2` |
| 系列名称、编码、色彩 | `material_series_v2` |
| 五行、标签、故事、保养、渲染参数 | `material_series_profiles_v2.profile_json` |
| 封面、图库 | `material_series_assets_v2` |
| 规格、等级、售价、成本、供应信息 | `material_skus_v2` |
| 现存、占用、安全库存 | `material_inventory_v2` |

旧表 `material_taxonomy`、`managed_materials` 和 `material_knowledge` 仅用于迁移期兼容，切换后不得作为库存或商品读取源。

## 切换策略

1. 执行 `20260807_25_material_catalog_v2`，创建 V2 表并在同一迁移中回填。
2. 保持 `MATERIAL_CATALOG_V2_ENABLED=false`，旧写入事务内影子同步 V2。
3. 调用 `GET /api/v1/admin/material-catalog-v2/status`；只有 `ready=true` 才允许切换。
4. 设置 `MATERIAL_CATALOG_V2_ENABLED=true` 并发布测试环境。
5. 管理端、公开材料接口、推荐和订单统一读取 V2；库存变更只写 `material_inventory_v2`。
6. 验证稳定后再删除兼容写入和旧表。本次迁移不删除旧表，避免不可逆切换。

## 回滚

- 应用回滚：关闭 `MATERIAL_CATALOG_V2_ENABLED` 并回滚服务版本。适用于尚未在 V2 产生库存交易的阶段。
- 切换后如已有交易，不能直接重新启用旧库存；需先维护窗口，将 V2 库存按 SKU 对账回灌旧表。
- 结构回滚：在确认无 V2 独占写入后执行 migration downgrade；该操作只删除六张 V2 表，不改旧表数据。
- 部署前由 blue/green 发布流程自动对测试库执行一致性备份。

## 验收门禁

- SKU 数量与旧目录一致，无孤儿类目、系列、SKU 或库存。
- 价格、尺寸、重量、启用状态逐项一致；切换前库存逐项一致。
- V2 库存满足 `0 <= reserved_stock <= stock`，安全库存非负。
- 详情页不调用完整 `/material-options`；仅异步缓存轻量 `/material-editor-options`。
- 下单预占、支付确认、取消释放、售后回库均只操作同一库存账本。
