const PREVIEW_STAGE_SIZE = 560;
const PREVIEW_CENTER = PREVIEW_STAGE_SIZE / 2;
const DEFAULT_WORKSPACE_CENTER = 288;
const MAX_PREVIEW_ITEMS = 40;

function firstImageUrl(item = {}) {
  const urls = (item.image_urls || item.image_pool || [])
    .concat(item.image_url || item.image || item.cover || [])
    .filter(url => typeof url === 'string' && url.trim());
  return urls[0] || '';
}

function placementCoordinate(placement = {}, axis = 'x', preferStringed = false) {
  const looseKey = axis === 'x' ? 'looseX' : 'looseY';
  const stringedValue = Number(placement[axis]);
  const looseValue = Number(placement[looseKey]);
  if (preferStringed && Number.isFinite(stringedValue)) return stringedValue;
  if (Number.isFinite(looseValue)) return looseValue;
  return stringedValue;
}

function hasSavedPlacement(placement = {}, preferStringed = false) {
  return Number.isFinite(placementCoordinate(placement, 'x', preferStringed))
    && Number.isFinite(placementCoordinate(placement, 'y', preferStringed));
}

function inferSourceOrigin(placements = [], design = {}) {
  const storedCenter = Number(
    design.workspaceStageCenter
    || design.previewSourceCenter
    || design.preview_source_center
  );
  if (Number.isFinite(storedCenter) && storedCenter >= 180 && storedCenter <= 480) {
    return { x: storedCenter, y: storedCenter, scaleBase: storedCenter };
  }
  const preferStringed = design.isLooseMode === false;
  const points = placements.map(placement => {
    const x = placementCoordinate(placement, 'x', preferStringed) + Number(placement.dx || 0);
    const y = placementCoordinate(placement, 'y', preferStringed) + Number(placement.dy || 0);
    return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
  }).filter(Boolean);
  if (points.length >= 3) {
    const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
    const y = points.reduce((sum, point) => sum + point.y, 0) / points.length;
    const scaleBase = (x + y) / 2;
    if (scaleBase >= 180 && scaleBase <= 480) return { x, y, scaleBase };
  }
  return {
    x: DEFAULT_WORKSPACE_CENTER,
    y: DEFAULT_WORKSPACE_CENTER,
    scaleBase: DEFAULT_WORKSPACE_CENTER
  };
}

function resolveBeadSize(item = {}, placement = {}, count = 0) {
  const placementSize = Number(placement.beadSize || placement.diameter);
  const sizeMm = Number(item.size || item.diameter || 0);
  const rawSize = Number.isFinite(placementSize) && placementSize > 0
    ? placementSize
    : (sizeMm ? sizeMm * 5.4 : 52);
  const maxSize = count >= 28 ? 46 : count >= 22 ? 50 : 58;
  return Math.max(30, Math.min(maxSize, rawSize));
}

function solveTangentRingRadius(beadSizes = []) {
  if (beadSizes.length < 3) return 156;
  const centerDistances = beadSizes.map((size, index) => (
    (size + beadSizes[(index + 1) % beadSizes.length]) / 2 + 2
  ));
  let low = Math.max(...centerDistances) / 2 + 0.01;
  let high = Math.max(480, beadSizes.reduce((sum, size) => sum + size, 0));
  for (let iteration = 0; iteration < 40; iteration += 1) {
    const radius = (low + high) / 2;
    const angleSum = centerDistances.reduce((sum, distance) => (
      sum + 2 * Math.asin(Math.min(1, distance / (2 * radius)))
    ), 0);
    if (angleSum > Math.PI * 2) low = radius;
    else high = radius;
  }
  return (low + high) / 2;
}

function buildRingGeometry(items = [], design = {}, initialSizes = []) {
  const count = Math.max(items.length, 1);
  const wristSize = Number(
    design.wristSize
    || design.wrist_size
    || (design.summary && design.summary.wristSize)
    || 16
  );
  const safeWrist = Number.isFinite(wristSize) ? Math.max(10, Math.min(25, wristSize)) : 16;
  const wristRadius = Math.round(166 + ((safeWrist - 10) / 15) * 28);
  let beadSizes = initialSizes.length ? initialSizes.slice() : items.map(() => 52);
  let radius = count >= 3 ? Math.max(wristRadius, solveTangentRingRadius(beadSizes)) : wristRadius;
  const maxOuterRadius = PREVIEW_CENTER - 30;
  const largestRadius = Math.max(...beadSizes, 1) / 2;
  if (radius + largestRadius > maxOuterRadius) {
    const scale = maxOuterRadius / (radius + largestRadius);
    beadSizes = beadSizes.map(size => Math.max(30, size * scale));
    radius = count >= 3
      ? Math.min(maxOuterRadius - Math.max(...beadSizes) / 2, solveTangentRingRadius(beadSizes))
      : Math.min(wristRadius, maxOuterRadius - Math.max(...beadSizes) / 2);
  }
  const points = items.map((item, index) => {
    const angle = -90 + (360 / count) * index;
    const radian = angle * Math.PI / 180;
    return {
      x: PREVIEW_CENTER + Math.cos(radian) * radius,
      y: PREVIEW_CENTER + Math.sin(radian) * radius,
      angle
    };
  });
  return { points, beadSizes };
}

function buildBeadBackground(item = {}) {
  return `radial-gradient(circle at 32% 28%, ${item.shine || '#fff'} 0 12%, ${item.color || '#d8d2c8'} 16% 60%, rgba(0,0,0,.20) 100%)`;
}

function buildDesignPreviewBeads(sequence = [], placements = [], design = {}) {
  const items = (sequence || []).slice(0, MAX_PREVIEW_ITEMS);
  if (!items.length) return [];
  const count = items.length;
  const savedPlacements = Array.isArray(placements) ? placements : [];
  const preferStringed = design.isLooseMode === false;
  const sourceOrigin = inferSourceOrigin(savedPlacements, design);
  const placementScale = PREVIEW_CENTER / sourceOrigin.scaleBase;
  const useSavedPlacements = savedPlacements.some(item => hasSavedPlacement(item, preferStringed));
  const initialSizes = items.map((item, index) => (
    resolveBeadSize(item, savedPlacements[index] || item.placement || {}, count)
  ));
  const ring = buildRingGeometry(items, design, initialSizes);

  return items.map((item, index) => {
    const placement = savedPlacements[index] || item.placement || {};
    const savedX = placementCoordinate(placement, 'x', preferStringed) + Number(placement.dx || 0);
    const savedY = placementCoordinate(placement, 'y', preferStringed) + Number(placement.dy || 0);
    const hasSavedPosition = useSavedPlacements && Number.isFinite(savedX) && Number.isFinite(savedY);
    const beadSize = hasSavedPosition
      ? Math.max(30, Math.min(62, (initialSizes[index] || 52) * placementScale))
      : (ring.beadSizes[index] || initialSizes[index] || 52);
    const ringPoint = ring.points[index] || { x: PREVIEW_CENTER, y: PREVIEW_CENTER, angle: 0 };
    const x = hasSavedPosition
      ? PREVIEW_CENTER + (savedX - sourceOrigin.x) * placementScale
      : ringPoint.x;
    const y = hasSavedPosition
      ? PREVIEW_CENTER + (savedY - sourceOrigin.y) * placementScale
      : ringPoint.y;
    const rotation = hasSavedPosition ? Number(placement.rotation || 0) : ringPoint.angle;
    const imageUrl = placement.image_url || firstImageUrl(item);
    return {
      key: `${item.id || item.sku || item.skuId || item.name || 'bead'}-${index}`,
      image_url: imageUrl,
      style: `width:${beadSize}rpx;height:${beadSize}rpx;background:${buildBeadBackground(item)};transform:translate3d(${(x - beadSize / 2).toFixed(1)}rpx,${(y - beadSize / 2).toFixed(1)}rpx,0) rotate(${rotation.toFixed(1)}deg);`
    };
  });
}

module.exports = {
  buildDesignPreviewBeads
};
