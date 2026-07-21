const PREVIEW_STAGE_SIZE = 560;
const PREVIEW_CENTER = PREVIEW_STAGE_SIZE / 2;
const DEFAULT_WORKSPACE_CENTER = 288;
const MAX_PREVIEW_ITEMS = 40;
const {
  resolveMaterialGeometry,
  stringedMaterialOffset,
  stringedMaterialRotationDeg
} = require('./materialGeometry');
const {
  beadCapRenderMetrics,
  beadCapSlotsFromPlacement,
  isBeadCap
} = require('./materialAttachments');

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
  const physical = resolveMaterialGeometry(item);
  const rawSize = Number.isFinite(placementSize) && placementSize > 0
    ? placementSize
    : physical.displaySizeRpx;
  const maxSize = count >= 28 ? 48 : count >= 22 ? 54 : 68;
  return Math.max(24, Math.min(maxSize, rawSize));
}

function resolvePreviewRotation(placement = {}, options = {}) {
  const fallback = Number(options.fallback);
  const savedRotation = Number(placement.rotation);
  if (options.preferStringed) {
    const x = Number(options.x);
    const y = Number(options.y);
    const originX = Number(options.originX);
    const originY = Number(options.originY);
    if ([x, y, originX, originY].every(Number.isFinite)) {
      return stringedMaterialRotationDeg(
        Math.atan2(y - originY, x - originX),
        options.physical || {}
      );
    }
  }
  if (Number.isFinite(savedRotation)) return savedRotation;
  return Number.isFinite(fallback) ? fallback : 0;
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

function buildRingGeometry(items = [], design = {}, initialSizes = [], initialSpacingSizes = []) {
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
  let spacingSizes = initialSpacingSizes.length ? initialSpacingSizes.slice() : beadSizes.slice();
  let radius = count >= 3 ? Math.max(wristRadius, solveTangentRingRadius(spacingSizes)) : wristRadius;
  const maxOuterRadius = PREVIEW_CENTER - 30;
  const largestRadius = Math.max(...beadSizes, 1) / 2;
  if (radius + largestRadius > maxOuterRadius) {
    const scale = maxOuterRadius / (radius + largestRadius);
    beadSizes = beadSizes.map(size => Math.max(24, size * scale));
    spacingSizes = spacingSizes.map(size => Math.max(6, size * scale));
    radius = count >= 3
      ? Math.min(maxOuterRadius - Math.max(...beadSizes) / 2, solveTangentRingRadius(spacingSizes))
      : Math.min(wristRadius, maxOuterRadius - Math.max(...beadSizes) / 2);
  }
  const angles = [-Math.PI / 2];
  for (let index = 1; index < count; index += 1) {
    const distance = (spacingSizes[index - 1] + spacingSizes[index]) / 2 + 2;
    angles.push(angles[index - 1] + 2 * Math.asin(Math.min(1, distance / (2 * radius))));
  }
  const points = items.map((item, index) => {
    const radian = angles[index] || -Math.PI / 2;
    const angle = radian * 180 / Math.PI;
    return {
      x: PREVIEW_CENTER + Math.cos(radian) * radius,
      y: PREVIEW_CENTER + Math.sin(radian) * radius,
      angle
    };
  });
  return { points, beadSizes, spacingSizes };
}

function buildBeadBackground(item = {}) {
  return `radial-gradient(circle at 32% 28%, ${item.shine || '#fff'} 0 12%, ${item.color || '#d8d2c8'} 16% 60%, rgba(0,0,0,.20) 100%)`;
}

function solve3x3(matrix, vector) {
  const values = matrix.map(row => row.slice());
  const result = vector.slice();
  for (let column = 0; column < 3; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < 3; row += 1) {
      if (Math.abs(values[row][column]) > Math.abs(values[pivot][column])) pivot = row;
    }
    if (Math.abs(values[pivot][column]) < 1e-6) return null;
    if (pivot !== column) {
      [values[pivot], values[column]] = [values[column], values[pivot]];
      [result[pivot], result[column]] = [result[column], result[pivot]];
    }
    const divisor = values[column][column];
    for (let index = column; index < 3; index += 1) values[column][index] /= divisor;
    result[column] /= divisor;
    for (let row = 0; row < 3; row += 1) {
      if (row === column) continue;
      const factor = values[row][column];
      for (let index = column; index < 3; index += 1) {
        values[row][index] -= factor * values[column][index];
      }
      result[row] -= factor * result[column];
    }
  }
  return result;
}

function fitPreviewCircle(points = []) {
  if (points.length < 3) return null;
  const sums = points.reduce((acc, point) => {
    const x = Number(point.x);
    const y = Number(point.y);
    const squared = x * x + y * y;
    acc.x += x;
    acc.y += y;
    acc.xx += x * x;
    acc.yy += y * y;
    acc.xy += x * y;
    acc.squared += squared;
    acc.xSquared += x * squared;
    acc.ySquared += y * squared;
    return acc;
  }, { x: 0, y: 0, xx: 0, yy: 0, xy: 0, squared: 0, xSquared: 0, ySquared: 0 });
  const solution = solve3x3([
    [sums.xx, sums.xy, sums.x],
    [sums.xy, sums.yy, sums.y],
    [sums.x, sums.y, points.length]
  ], [-sums.xSquared, -sums.ySquared, -sums.squared]);
  if (!solution) return null;
  const x = -solution[0] / 2;
  const y = -solution[1] / 2;
  const radius = points.reduce((sum, point) => (
    sum + Math.sqrt((point.x - x) ** 2 + (point.y - y) ** 2)
  ), 0) / points.length;
  if (![x, y, radius].every(Number.isFinite) || radius <= 0) return null;
  return { x, y, radius };
}

function buildDesignPreviewGuide(beads = [], design = {}) {
  if (design.isLooseMode === true || beads.length < 3) {
    return { visible: false, style: '', centerX: 0, centerY: 0, radius: 0 };
  }
  const points = beads.filter(item => !item.isAttachment).map(item => ({
    x: Number.isFinite(item.previewAnchorX) ? item.previewAnchorX : item.previewX,
    y: Number.isFinite(item.previewAnchorY) ? item.previewAnchorY : item.previewY
  }))
    .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y));
  const circle = fitPreviewCircle(points);
  if (!circle) return { visible: false, style: '', centerX: 0, centerY: 0, radius: 0 };
  const diameter = circle.radius * 2;
  return {
    visible: true,
    centerX: circle.x,
    centerY: circle.y,
    radius: circle.radius,
    style: `left:${(circle.x - circle.radius).toFixed(1)}rpx;top:${(circle.y - circle.radius).toFixed(1)}rpx;width:${diameter.toFixed(1)}rpx;height:${diameter.toFixed(1)}rpx;`
  };
}

function buildDesignPreviewBeads(sequence = [], placements = [], design = {}) {
  const sequenceItems = sequence || [];
  const items = sequenceItems.filter(item => (
    !isBeadCap(item)
    && item.attachment_mode !== 'bead_cap'
    && !(item.attachment && item.attachment.mode === 'bead_cap')
  )).slice(0, MAX_PREVIEW_ITEMS);
  if (!items.length) return [];
  const count = items.length;
  const savedPlacements = Array.isArray(placements) ? placements : [];
  const resolvedPlacements = items.map((item, index) => (
    savedPlacements[index] || item.placement || {}
  ));
  const preferStringed = design.isLooseMode === false;
  const sourceOrigin = inferSourceOrigin(resolvedPlacements, design);
  const placementScale = PREVIEW_CENTER / sourceOrigin.scaleBase;
  const useSavedPlacements = resolvedPlacements.some(item => hasSavedPlacement(item, preferStringed));
  const initialSizes = items.map((item, index) => (
    resolveBeadSize(item, resolvedPlacements[index], count)
  ));
  const physicalSpecs = items.map(item => resolveMaterialGeometry(item));
  const initialSpacingSizes = physicalSpecs.map((physical, index) => (
    physical.spacingSizeRpx * initialSizes[index] / Math.max(1, physical.displaySizeRpx)
  ));
  const ring = buildRingGeometry(items, design, initialSizes, initialSpacingSizes);

  const beads = items.map((item, index) => {
    const placement = resolvedPlacements[index];
    const physical = physicalSpecs[index];
    const savedX = placementCoordinate(placement, 'x', preferStringed) + Number(placement.dx || 0);
    const savedY = placementCoordinate(placement, 'y', preferStringed) + Number(placement.dy || 0);
    const hasSavedPosition = useSavedPlacements && Number.isFinite(savedX) && Number.isFinite(savedY);
    const beadSize = hasSavedPosition
      ? Math.max(30, Math.min(62, (initialSizes[index] || 52) * placementScale))
      : (ring.beadSizes[index] || initialSizes[index] || 52);
    const ringPoint = ring.points[index] || { x: PREVIEW_CENTER, y: PREVIEW_CENTER, angle: 0 };
    const anchorX = hasSavedPosition
      ? PREVIEW_CENTER + (savedX - sourceOrigin.x) * placementScale
      : ringPoint.x;
    const anchorY = hasSavedPosition
      ? PREVIEW_CENTER + (savedY - sourceOrigin.y) * placementScale
      : ringPoint.y;
    const offset = preferStringed
      ? stringedMaterialOffset(physical, beadSize / Math.max(1, physical.displaySizeRpx))
      : { x: 0, y: 0 };
    const x = anchorX + offset.x;
    const y = anchorY + offset.y;
    const rotation = hasSavedPosition
      ? resolvePreviewRotation(placement, {
        preferStringed,
        x: savedX,
        y: savedY,
        originX: sourceOrigin.x,
        originY: sourceOrigin.y,
        physical,
        fallback: ringPoint.angle
      })
      : (preferStringed
        ? stringedMaterialRotationDeg(ringPoint.angle * Math.PI / 180, physical)
        : ringPoint.angle);
    const imageUrl = placement.image_url || firstImageUrl(item);
    return {
      key: `${item.id || item.sku || item.skuId || item.name || 'bead'}-${index}`,
      image_url: imageUrl,
      previewX: x,
      previewY: y,
      previewAnchorX: anchorX,
      previewAnchorY: anchorY,
      previewSize: beadSize,
      attachmentAxisRotation: preferStringed ? ringPoint.angle + 90 : rotation,
      fallbackStyle: `background:${buildBeadBackground(item)};`,
      style: `width:${beadSize}rpx;height:${beadSize}rpx;background:transparent;transform:translate3d(${(x - beadSize / 2).toFixed(1)}rpx,${(y - beadSize / 2).toFixed(1)}rpx,0) rotate(${rotation.toFixed(1)}deg);`
    };
  });
  const capSlots = resolvedPlacements.map(placement => beadCapSlotsFromPlacement(placement));
  sequenceItems.filter(item => (
    isBeadCap(item)
    || item.attachment_mode === 'bead_cap'
    || item.attachment && item.attachment.mode === 'bead_cap'
  )).forEach(cap => {
    const attachment = cap.attachment || cap.placement || {};
    const hostIndex = Number(attachment.host_index || attachment.hostIndex) - 1;
    const side = attachment.side;
    if (!Number.isInteger(hostIndex) || hostIndex < 0 || hostIndex >= capSlots.length) return;
    if (side !== 'left' && side !== 'right') return;
    capSlots[hostIndex] = { ...(capSlots[hostIndex] || {}), [side]: cap };
  });
  const capBeads = [];
  beads.forEach((host, hostIndex) => {
    const slots = capSlots[hostIndex] || {};
    ['left', 'right'].forEach(side => {
      const cap = slots[side];
      if (!cap) return;
      const direction = side === 'left' ? -1 : 1;
      const axisRotation = Number(host.attachmentAxisRotation) || 0;
      const radians = axisRotation * Math.PI / 180;
      const metrics = beadCapRenderMetrics({
        item: items[hostIndex] || {},
        size: host.previewSize
      }, cap);
      const capWidth = metrics.width;
      const capHeight = metrics.height;
      const capSize = metrics.size;
      const offset = metrics.offset * direction;
      const x = host.previewX + Math.cos(radians) * offset;
      const y = host.previewY + Math.sin(radians) * offset;
      capBeads.push({
        key: `${host.key}-cap-${side}-${cap.id || cap.sku || cap.skuId || 'item'}`,
        image_url: cap.image_url || firstImageUrl(cap),
        previewX: x,
        previewY: y,
        previewAnchorX: host.previewAnchorX,
        previewAnchorY: host.previewAnchorY,
        previewSize: capSize,
        isAttachment: true,
        fallbackStyle: `background:${buildBeadBackground(cap)};`,
        style: `width:${capWidth.toFixed(1)}rpx;height:${capHeight.toFixed(1)}rpx;background:transparent;transform:translate3d(${(x - capWidth / 2).toFixed(1)}rpx,${(y - capHeight / 2).toFixed(1)}rpx,0) rotate(${axisRotation.toFixed(1)}deg) scaleX(${side === 'right' ? -1 : 1});`
      });
    });
  });
  return [...beads, ...capBeads];
}

module.exports = {
  buildDesignPreviewBeads,
  buildDesignPreviewGuide
};
