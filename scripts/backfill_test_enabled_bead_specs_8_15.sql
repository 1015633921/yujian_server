-- 测试环境专用：把当前启用珠子品种的 8–15mm 规格补齐，并统一为 0.01 元。
-- 执行前置条件：MySQL 8+；只允许在 yujian_test 执行。
-- 影响范围：执行时已存在启用 SKU 的 bead 品种；不处理配件、吊坠或停用的整个品种。
-- 回滚：本脚本会在当前数据库创建 bak_test_enabled_bead_specs_20260807，
--        下方保留了基于该备份表的回滚 SQL。

CREATE TEMPORARY TABLE _bead_spec_scope AS
SELECT DISTINCT COALESCE(NULLIF(series_id, ''), NULLIF(material_code, ''), series) AS variety_key
FROM managed_materials
WHERE top = 'bead' AND enabled = 1;

CREATE TEMPORARY TABLE _bead_spec_sizes (size DOUBLE PRIMARY KEY);
INSERT INTO _bead_spec_sizes (size) VALUES (8), (9), (10), (11), (12), (13), (14), (15);

-- 不能覆盖既有备份，避免误执行第二次后失去原始回滚点。
CREATE TABLE bak_test_enabled_bead_specs_20260807 LIKE managed_materials;
INSERT INTO bak_test_enabled_bead_specs_20260807
SELECT material.*
FROM managed_materials AS material
JOIN _bead_spec_scope AS scope
  ON COALESCE(NULLIF(material.series_id, ''), NULLIF(material.material_code, ''), material.series) = scope.variety_key
JOIN _bead_spec_sizes AS target ON target.size = material.size
WHERE material.top = 'bead';

CREATE TEMPORARY TABLE _bead_spec_missing AS
SELECT scope.variety_key, target.size AS target_size
FROM _bead_spec_scope AS scope
CROSS JOIN _bead_spec_sizes AS target
LEFT JOIN managed_materials AS existing
  ON COALESCE(NULLIF(existing.series_id, ''), NULLIF(existing.material_code, ''), existing.series) = scope.variety_key
 AND existing.top = 'bead'
 AND existing.size = target.size
WHERE existing.id IS NULL;

-- 每个缺失规格从同品种、尺寸最接近的已启用 SKU 复制非规格字段。
CREATE TEMPORARY TABLE _bead_spec_seed AS
SELECT variety_key, target_size, source_id
FROM (
  SELECT missing.variety_key, missing.target_size, source.id AS source_id,
         ROW_NUMBER() OVER (
           PARTITION BY missing.variety_key, missing.target_size
           ORDER BY ABS(source.size - missing.target_size), source.size, source.id
         ) AS source_rank
  FROM _bead_spec_missing AS missing
  JOIN managed_materials AS source
    ON COALESCE(NULLIF(source.series_id, ''), NULLIF(source.material_code, ''), source.series) = missing.variety_key
   AND source.top = 'bead'
   AND source.enabled = 1
) AS ranked
WHERE source_rank = 1;

SET @bead_spec_timestamp = DATE_FORMAT(UTC_TIMESTAMP(), '%Y-%m-%dT%H:%i:%s+00:00');
SELECT GREATEST(1000000000000, COALESCE(MAX(CAST(skuId AS UNSIGNED)), 0))
INTO @bead_spec_next_sku
FROM managed_materials
WHERE skuId REGEXP '^[0-9]+$';

START TRANSACTION;

-- 既有的目标规格（包括之前被停用的规格）恢复启用，并同步测试售价。
UPDATE managed_materials AS material
JOIN _bead_spec_scope AS scope
  ON COALESCE(NULLIF(material.series_id, ''), NULLIF(material.material_code, ''), material.series) = scope.variety_key
JOIN _bead_spec_sizes AS target ON target.size = material.size
SET material.price = 0.01,
    material.price_cents = 1,
    material.enabled = 1,
    material.updated_at = @bead_spec_timestamp,
    material.revision = material.revision + 1
WHERE material.top = 'bead';

-- 缺失规格继承最近 SKU 的品种资料、库存和物理参数；重量按珠径立方比例估算。
INSERT INTO managed_materials (
  id, skuId, top, category, series, grade, name, effect, element,
  price, price_cents, size, weight, color, shine, image_path, image_url,
  enabled, sort_order, created_at, updated_at, stock, image_urls_json,
  material_code, cost_price, safety_stock, supplier_name, purchase_note,
  reserved_stock, physical_specs_json, series_id, revision
)
SELECT
  CONCAT('mat_test_spec_', REPLACE(UUID(), '-', '')),
  CAST(@bead_spec_next_sku + ROW_NUMBER() OVER (ORDER BY seed.variety_key, seed.target_size) AS CHAR),
  source.top, source.category, source.series, source.grade, source.name, source.effect, source.element,
  0.01, 1, seed.target_size,
  ROUND(source.weight * POW(seed.target_size / NULLIF(source.size, 0), 3), 2),
  source.color, source.shine, source.image_path, source.image_url,
  1, source.sort_order + CAST((seed.target_size - source.size) * 10 AS SIGNED),
  @bead_spec_timestamp, @bead_spec_timestamp, source.stock, source.image_urls_json,
  source.material_code, source.cost_price, source.safety_stock, source.supplier_name, source.purchase_note,
  0, source.physical_specs_json, source.series_id, 1
FROM _bead_spec_seed AS seed
JOIN managed_materials AS source ON source.id = seed.source_id;

COMMIT;

-- 验收：目标范围应为 52 个品种 × 8 个规格 = 416 行，且没有停用或非 0.01 元记录。
SELECT
  COUNT(*) AS target_skus,
  COUNT(DISTINCT COALESCE(NULLIF(material.series_id, ''), NULLIF(material.material_code, ''), material.series)) AS target_varieties,
  SUM(material.enabled = 1) AS enabled_skus,
  SUM(material.enabled = 0) AS disabled_skus,
  SUM(material.price = 0.01 AND material.price_cents = 1) AS price_synced_skus,
  SUM(material.price <> 0.01 OR material.price_cents <> 1) AS invalid_price_skus
FROM managed_materials AS material
JOIN _bead_spec_scope AS scope
  ON COALESCE(NULLIF(material.series_id, ''), NULLIF(material.material_code, ''), material.series) = scope.variety_key
JOIN _bead_spec_sizes AS target ON target.size = material.size
WHERE material.top = 'bead';

-- 回滚（确认需要恢复本次执行前的数据时再单独执行）：
-- START TRANSACTION;
-- DELETE material
-- FROM managed_materials AS material
-- JOIN (
--   SELECT DISTINCT COALESCE(NULLIF(series_id, ''), NULLIF(material_code, ''), series) AS variety_key
--   FROM bak_test_enabled_bead_specs_20260807
-- ) AS scope
--   ON COALESCE(NULLIF(material.series_id, ''), NULLIF(material.material_code, ''), material.series) = scope.variety_key
-- WHERE material.top = 'bead' AND material.size BETWEEN 8 AND 15;
-- INSERT INTO managed_materials SELECT * FROM bak_test_enabled_bead_specs_20260807;
-- COMMIT;
