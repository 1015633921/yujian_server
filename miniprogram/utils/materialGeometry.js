const DEFAULT_MM_TO_RPX = 5.4;
const ROUND_SHAPES = new Set(['round', 'faceted_round']);
const RECTANGULAR_SHAPES = new Set([
  'barrel',
  'cube',
  'double_terminated',
  'single_terminated',
  'triangle',
  'curved_tube',
  'connector',
  'clasp',
  'charm'
]);

function positiveNumber(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number) && number > 0) return number;
  }
  return 0;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function roundMetric(value) {
  return Number(Number(value).toFixed(3));
}

function materialParams(item = {}) {
  const visual = item.visual || {};
  return {
    ...((visual && visual.material_params) || {}),
    ...(item.material_params || {}),
    ...(item.physical_specs || {})
  };
}

function resolveMaterialGeometry(item = {}, options = {}) {
  const params = materialParams(item);
  const sku = item.sku || {};
  const top = sku.top || item.top || 'bead';
  const sizeMm = positiveNumber(
    sku.size_mm,
    item.size,
    item.size_mm,
    item.diameter,
    options.defaultSizeMm,
    8
  );
  const shape = String(params.bead_shape || (top === 'bead' ? 'round' : 'special'));
  const isRound = ROUND_SHAPES.has(shape);
  const bodyWidthMm = positiveNumber(params.body_width_mm, sizeMm);
  const bodyHeightMm = positiveNumber(params.body_height_mm, sizeMm);
  const stringAxisWidthMm = positiveNumber(params.string_axis_width_mm, sizeMm);
  const displayExtentMm = Math.max(sizeMm, bodyWidthMm, bodyHeightMm);
  const scale = positiveNumber(options.mmToRpx, DEFAULT_MM_TO_RPX);
  const displaySizeRpx = roundMetric(clamp(
    displayExtentMm * scale,
    isRound ? 42 : 24,
    Number(options.maxDisplayRpx) || 96
  ));
  const displayScale = displaySizeRpx / displayExtentMm;
  const collisionWidthRpx = roundMetric(clamp(bodyWidthMm * displayScale, 10, displaySizeRpx));
  const collisionHeightRpx = roundMetric(clamp(bodyHeightMm * displayScale, 10, displaySizeRpx));
  const spacingSizeRpx = roundMetric(clamp(stringAxisWidthMm * displayScale, 6, displaySizeRpx));
  const rawAxis = Number(params.image_string_axis_deg);
  const imageStringAxisDeg = Number.isFinite(rawAxis) ? ((rawAxis % 180) + 180) % 180 : 90;
  const placementMode = ['hanging', 'attached_side'].includes(params.placement_mode)
    ? params.placement_mode
    : 'threaded';
  const isAttachedSide = placementMode === 'attached_side' || shape === 'bead_cap';
  const hasExplicitDimensions = ['string_axis_width_mm', 'body_width_mm', 'body_height_mm']
    .every(key => positiveNumber(params[key]) > 0);
  const collisionShape = !isRound && (
    RECTANGULAR_SHAPES.has(shape)
    || Math.max(collisionWidthRpx, collisionHeightRpx) / Math.max(1, Math.min(collisionWidthRpx, collisionHeightRpx)) > 1.15
  ) ? 'rectangle' : 'circle';

  return {
    shape,
    shapeClass: `shape-${shape.replace(/[^a-z0-9_-]/gi, '-')}`,
    isRound,
    placementMode,
    imageStringAxisDeg,
    sizeMm,
    stringAxisWidthMm,
    bodyWidthMm,
    bodyHeightMm,
    displayExtentMm,
    displaySizeRpx,
    spacingSizeRpx,
    collisionWidthRpx,
    collisionHeightRpx,
    collisionShape,
    isAttachedSide,
    compatibleBeadSizeMm: positiveNumber(params.compatible_bead_size_mm),
    compatibleSizeToleranceMm: positiveNumber(params.compatible_size_tolerance_mm, 0.6),
    specComplete: isAttachedSide
      ? hasExplicitDimensions && positiveNumber(params.compatible_bead_size_mm) > 0
      : (isRound || hasExplicitDimensions),
    cardSpecText: isRound
      ? `${sizeMm}mm`
      : (hasExplicitDimensions ? `${bodyWidthMm}×${bodyHeightMm}mm` : '规格待补'),
    specText: isRound
      ? `${sizeMm}mm`
      : (hasExplicitDimensions
        ? `占位${stringAxisWidthMm}mm · ${bodyWidthMm}×${bodyHeightMm}mm`
        : '规格待补充')
  };
}

function stringedMaterialRotationDeg(angleRad, itemOrSpec = {}) {
  const spec = itemOrSpec.displaySizeRpx ? itemOrSpec : resolveMaterialGeometry(itemOrSpec);
  if (spec.placementMode === 'hanging') return 0;
  const tangentDeg = Number(angleRad || 0) * 180 / Math.PI + 90;
  let rotation = tangentDeg - spec.imageStringAxisDeg;
  while (rotation > 180) rotation -= 360;
  while (rotation <= -180) rotation += 360;
  return rotation;
}

function stringedMaterialOffset(itemOrSpec = {}, scale = 1) {
  const spec = itemOrSpec.displaySizeRpx ? itemOrSpec : resolveMaterialGeometry(itemOrSpec);
  if (spec.placementMode !== 'hanging') return { x: 0, y: 0 };
  return { x: 0, y: spec.displaySizeRpx * 0.34 * (Number(scale) || 1) };
}

module.exports = {
  materialParams,
  resolveMaterialGeometry,
  stringedMaterialOffset,
  stringedMaterialRotationDeg
};
