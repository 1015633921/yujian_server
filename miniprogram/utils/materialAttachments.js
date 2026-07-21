const { materialParams, resolveMaterialGeometry } = require('./materialGeometry');

const DEFAULT_COMPATIBILITY_TOLERANCE_MM = 0.6;

function positiveNumber(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number) && number > 0) return number;
  }
  return 0;
}

function isBeadCap(item = {}) {
  const params = materialParams(item);
  return params.placement_mode === 'attached_side' || params.bead_shape === 'bead_cap';
}

function materialSizeMm(item = {}) {
  const sku = item.sku && typeof item.sku === 'object' ? item.sku : {};
  return positiveNumber(sku.size_mm, item.size, item.size_mm, item.diameter);
}

function beadCapCompatibility(cap = {}, host = {}) {
  if (!isBeadCap(cap) || isBeadCap(host)) {
    return { compatible: false, targetSizeMm: 0, hostSizeMm: materialSizeMm(host), toleranceMm: 0 };
  }
  const hostGeometry = resolveMaterialGeometry(host);
  if (hostGeometry.placementMode !== 'threaded' || !hostGeometry.isRound) {
    return { compatible: false, targetSizeMm: 0, hostSizeMm: hostGeometry.sizeMm, toleranceMm: 0 };
  }
  const params = materialParams(cap);
  const targetSizeMm = positiveNumber(params.compatible_bead_size_mm);
  const toleranceMm = positiveNumber(
    params.compatible_size_tolerance_mm,
    DEFAULT_COMPATIBILITY_TOLERANCE_MM
  );
  const hostSizeMm = hostGeometry.sizeMm;
  return {
    compatible: targetSizeMm > 0 && Math.abs(hostSizeMm - targetSizeMm) <= toleranceMm,
    targetSizeMm,
    hostSizeMm,
    toleranceMm
  };
}

function attachmentFromMaterial(material = {}, imageUrl = '') {
  const sku = material.sku && typeof material.sku === 'object' ? material.sku : {};
  const params = materialParams(material);
  return {
    id: material.id || material.material_id || material.skuId || material.sku_id || sku.id || sku.sku_id || '',
    material_id: material.id || material.material_id || '',
    skuId: material.skuId || material.sku_id || sku.id || sku.sku_id || '',
    top: material.top || sku.top || 'accessory',
    name: material.display_name || material.name || sku.name || '包珠隔片',
    category: material.category || sku.category || '',
    series: material.series || sku.series || '',
    size: materialSizeMm(material),
    price: Number(material.price ?? material.priceText ?? material.amount ?? sku.price_per_bead ?? 0) || 0,
    weight: Number(material.weight ?? sku.weight_g ?? 0) || 0,
    stock: Number(material.stock ?? sku.stock ?? 0),
    stock_status: material.stock_status || sku.stock_status || '',
    enabled: material.enabled ?? sku.enabled,
    image_url: imageUrl || material.image_url || '',
    image_urls: Array.isArray(material.image_urls) ? material.image_urls : [],
    material_params: params,
    attachment_mode: 'bead_cap'
  };
}

function beadCapSlotsFromPlacement(placement = {}) {
  const source = placement.bead_caps || placement.beadCaps || {};
  const slots = {};
  if (source.left && isBeadCap(source.left)) slots.left = { ...source.left };
  if (source.right && isBeadCap(source.right)) slots.right = { ...source.right };
  return slots;
}

function beadCapItemsFromPlacements(placements = []) {
  return (placements || []).flatMap((placement, hostIndex) => {
    const slots = beadCapSlotsFromPlacement(placement);
    return ['left', 'right'].map(side => slots[side]
      ? { ...slots[side], side, hostIndex }
      : null).filter(Boolean);
  });
}

function beadCapTotals(placements = []) {
  const items = beadCapItemsFromPlacements(placements);
  return {
    count: items.length,
    price: items.reduce((sum, item) => sum + Number(item.price || 0), 0),
    weight: items.reduce((sum, item) => sum + Number(item.weight || 0), 0),
    items
  };
}

function beadCapRenderMetrics(hostSprite = {}, attachment = {}) {
  const hostSize = Math.max(8, Number(hostSprite.size) || 48);
  const hostGeometry = resolveMaterialGeometry(hostSprite.item || {});
  const capGeometry = resolveMaterialGeometry(attachment || {});
  const referenceSizeMm = positiveNumber(hostGeometry.sizeMm, capGeometry.compatibleBeadSizeMm, 8);
  const pixelsPerMm = hostSize / referenceSizeMm;
  const width = Math.max(
    hostSize * 0.22,
    Math.min(hostSize * 1.35, capGeometry.bodyWidthMm * pixelsPerMm)
  );
  const height = Math.max(
    hostSize * 0.16,
    Math.min(hostSize * 1.35, capGeometry.bodyHeightMm * pixelsPerMm)
  );
  return {
    width,
    height,
    size: Math.max(width, height),
    offset: Math.max(hostSize * 0.22, hostSize * 0.5 - width * 0.16)
  };
}

function beadCapSprite(hostSprite = {}, attachment = {}, side = 'right') {
  if (!hostSprite.item || !attachment || !isBeadCap(attachment)) return null;
  const axisRotation = Number(hostSprite.attachmentAxisRotation ?? hostSprite.rotation) || 0;
  const radians = axisRotation * Math.PI / 180;
  const metrics = beadCapRenderMetrics(hostSprite, attachment);
  const direction = side === 'left' ? -1 : 1;
  return {
    item: attachment,
    x: Number(hostSprite.x) + Math.cos(radians) * metrics.offset * direction,
    y: Number(hostSprite.y) + Math.sin(radians) * metrics.offset * direction,
    size: metrics.size,
    drawWidth: metrics.width,
    drawHeight: metrics.height,
    rotation: axisRotation,
    mirrorX: side === 'right',
    attachedAccessory: true,
    attachmentSide: side,
    hostIndex: hostSprite.index,
    index: hostSprite.index,
    logicalX: hostSprite.logicalX,
    logicalY: hostSprite.logicalY,
    logicalSize: hostSprite.logicalSize,
    noShadow: true,
    screenSpace: false
  };
}

module.exports = {
  DEFAULT_COMPATIBILITY_TOLERANCE_MM,
  attachmentFromMaterial,
  beadCapCompatibility,
  beadCapItemsFromPlacements,
  beadCapSlotsFromPlacement,
  beadCapSprite,
  beadCapRenderMetrics,
  beadCapTotals,
  isBeadCap
};
