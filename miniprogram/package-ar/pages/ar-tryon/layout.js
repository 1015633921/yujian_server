const clamp = (value, min, max) => Math.max(min, Math.min(max, Number(value) || 0));

function itemSizeMm(item = {}) {
  const params = item.material_params || {};
  const size = Number(
    item.size
    || item.diameter
    || params.body_width_mm
    || params.string_axis_width_mm
    || 8
  );
  return Number.isFinite(size) && size > 0 ? size : 8;
}

function itemAspectRatio(item = {}) {
  const params = item.material_params || {};
  const width = Number(params.body_width_mm || item.body_width_mm || itemSizeMm(item));
  const height = Number(params.body_height_mm || item.body_height_mm || itemSizeMm(item));
  if (!(width > 0) || !(height > 0)) return 1;
  return clamp(height / width, 0.42, 2.4);
}

function buildBraceletLayout({
  items = [],
  width = 375,
  height = 667,
  centerX,
  centerY,
  scale = 1,
  rotation = 0
} = {}) {
  const safeItems = Array.isArray(items) ? items.filter(Boolean) : [];
  const viewportWidth = Math.max(240, Number(width) || 375);
  const viewportHeight = Math.max(400, Number(height) || 667);
  const safeScale = clamp(scale, 0.58, 1.48);
  const pxPerMm = 2.42 * safeScale;
  const totalWidthPx = safeItems.reduce((sum, item) => sum + itemSizeMm(item) * pxPerMm, 0);
  const radiusX = clamp(totalWidthPx / 4.38, viewportWidth * 0.22, viewportWidth * 0.40);
  const radiusY = clamp(radiusX * 0.31, 24, viewportHeight * 0.13);
  const cx = Number.isFinite(Number(centerX)) ? Number(centerX) : viewportWidth / 2;
  const cy = Number.isFinite(Number(centerY)) ? Number(centerY) : viewportHeight * 0.45;
  const wholeRotation = Number(rotation) || 0;
  const cosRotation = Math.cos(wholeRotation);
  const sinRotation = Math.sin(wholeRotation);
  const count = Math.max(1, safeItems.length);

  return safeItems.map((item, index) => {
    const angle = -Math.PI / 2 + Math.PI * 2 * index / count;
    const localX = Math.cos(angle) * radiusX;
    const localY = Math.sin(angle) * radiusY;
    const x = cx + localX * cosRotation - localY * sinRotation;
    const y = cy + localX * sinRotation + localY * cosRotation;
    const widthPx = clamp(itemSizeMm(item) * pxPerMm, 14, 42);
    const heightPx = clamp(widthPx * itemAspectRatio(item), 12, 48);
    const isBack = Math.sin(angle) < 0;
    const params = item.material_params || {};
    const imageAxisDeg = Number(params.image_string_axis_deg || item.image_string_axis_deg || 0);
    return {
      index,
      item,
      x,
      y,
      width: widthPx,
      height: heightPx,
      angle,
      drawRotation: wholeRotation + angle + Math.PI / 2 + imageAxisDeg * Math.PI / 180,
      isBack,
      opacity: isBack ? 0.22 : 1
    };
  }).sort((a, b) => Number(b.isBack) - Number(a.isBack) || a.y - b.y);
}

module.exports = {
  buildBraceletLayout,
  itemAspectRatio,
  itemSizeMm
};
