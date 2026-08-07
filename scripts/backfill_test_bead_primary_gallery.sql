-- Test environment only: yujian_test
-- Adds the existing display image as the one-image gallery fallback for bead
-- varieties whose gallery is empty. The script preserves asset-version history
-- and records the change in the material audit log.

START TRANSACTION;

SET @backfill_at = DATE_FORMAT(UTC_TIMESTAMP(6), '%Y-%m-%dT%H:%i:%s.%fZ');

CREATE TEMPORARY TABLE target_bead_series AS
SELECT
  s.item_id,
  s.name,
  s.image_url,
  COALESCE(s.image_urls_json, '[]') AS previous_image_urls_json,
  GREATEST(COALESCE(s.asset_version, 1), 1) AS previous_asset_version
FROM material_taxonomy AS s
WHERE s.top = 'bead'
  AND s.kind = 'series'
  AND TRIM(COALESCE(s.image_url, '')) <> ''
  AND LOWER(TRIM(COALESCE(s.image_urls_json, ''))) IN ('', '[]', '{}', 'null');

-- Review the exact rows before the update. The current test environment should
-- show 12 series / 95 affected SKU records through the public materials API.
SELECT item_id, name, image_url, previous_image_urls_json, previous_asset_version
FROM target_bead_series
ORDER BY name, item_id;

UPDATE material_taxonomy AS s
JOIN target_bead_series AS t ON t.item_id = s.item_id
SET
  s.image_urls_json = JSON_ARRAY(s.image_url),
  s.asset_version = t.previous_asset_version + 1,
  s.updated_at = @backfill_at
WHERE s.asset_version = t.previous_asset_version;

INSERT INTO material_asset_versions
  (version_id, series_id, asset_version, image_url, image_urls_json, source, actor_id, created_at)
SELECT
  CONCAT('matasset_', LOWER(HEX(RANDOM_BYTES(12)))),
  s.item_id,
  s.asset_version,
  s.image_url,
  s.image_urls_json,
  'primary_gallery_backfill',
  'system_sql',
  @backfill_at
FROM material_taxonomy AS s
JOIN target_bead_series AS t ON t.item_id = s.item_id
WHERE s.asset_version = t.previous_asset_version + 1
  AND s.image_urls_json = JSON_ARRAY(s.image_url);

INSERT INTO material_audit_logs
  (log_id, action, target_type, target_id, material_id, material_code, actor_id, actor_name, summary, before_json, after_json, created_at)
SELECT
  CONCAT('matlog_', LOWER(HEX(RANDOM_BYTES(12)))),
  'series_gallery_update',
  'material_taxonomy',
  s.item_id,
  '',
  s.material_code,
  'system_sql',
  '测试环境 SQL 回填',
  CONCAT('主图补图库：', s.name),
  JSON_OBJECT('image_urls_json', t.previous_image_urls_json, 'asset_version', t.previous_asset_version),
  JSON_OBJECT('image_urls_json', s.image_urls_json, 'asset_version', s.asset_version),
  @backfill_at
FROM material_taxonomy AS s
JOIN target_bead_series AS t ON t.item_id = s.item_id
WHERE s.asset_version = t.previous_asset_version + 1
  AND s.image_urls_json = JSON_ARRAY(s.image_url);

SELECT
  COUNT(*) AS updated_series,
  SUM(JSON_LENGTH(image_urls_json) = 1) AS one_image_gallery_series
FROM material_taxonomy
WHERE item_id IN (SELECT item_id FROM target_bead_series);

COMMIT;
