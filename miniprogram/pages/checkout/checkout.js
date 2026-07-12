const auth = require('../../utils/auth');
const { effectiveWristText } = require('../../utils/designSummary');
const env = require('../../config/env');
const { createOrder, mockPayOrder, getMaterials } = require('../../utils/api');
const { assetUrl } = require('../../utils/assets');

const MATERIALS = {
  clearQuartz8: { name: '喜马拉雅白水晶 8mm', sku: 'SKU_CLEAR_8MM', price: 5 },
  clearQuartz10: { name: '喜马拉雅白水晶 10mm', sku: 'SKU_CLEAR_10MM', price: 10 },
  clearQuartz12: { name: '喜马拉雅白水晶 12mm', sku: 'SKU_CLEAR_12MM', price: 15 },
  clearQuartz14: { name: '喜马拉雅白水晶 14mm', sku: 'SKU_CLEAR_14MM', price: 18 },
  amethyst8: { name: '乌拉圭紫水晶 8mm', sku: 'SKU_AMETHYST_8MM', price: 12 },
  amethyst10: { name: '乌拉圭紫水晶 10mm', sku: 'SKU_AMETHYST_10MM', price: 18 },
  citrine8: { name: '巴西黄水晶 8mm', sku: 'SKU_CITRINE_8MM', price: 16 },
  citrine10: { name: '巴西黄水晶 10mm', sku: 'SKU_CITRINE_10MM', price: 22 },
  obsidian10: { name: '冰种黑曜石 10mm', sku: 'SKU_OBSIDIAN_10MM', price: 14 },
  tigerEye8: { name: '南非虎眼石 8mm', sku: 'SKU_TIGER_8MM', price: 13 },
  moonstone6: { name: '雪花幽灵 6mm', sku: 'SKU_MOON_6MM', price: 4 },
  moonstone8: { name: '雪花幽灵 8mm', sku: 'SKU_MOON_8MM', price: 8 },
  aquamarine8: { name: '巴西海蓝宝 8mm', sku: 'SKU_AQUA_8MM', price: 25 },
  roseQuartz8: { name: '马达加斯加粉晶 8mm', sku: 'SKU_ROSE_8MM', price: 11 },
  silverSpacer: { name: '纯银隔片', sku: 'SKU_SILVER_SPACER', price: 18 },
  goldSpacer: { name: '镀金隔片', sku: 'SKU_GOLD_SPACER', price: 16 },
  foxPendant: { name: '粉晶狐狸吊坠', sku: 'SKU_FOX_PENDANT', price: 88 }
};

const ADDRESS_KEY = 'checkoutReceiver';
const TRAY_THEME_STORAGE_KEY = 'workspaceTrayThemeV1';
const CHECKOUT_PREVIEW_STAGE_SIZE = 560;
const CHECKOUT_PREVIEW_CENTER = CHECKOUT_PREVIEW_STAGE_SIZE / 2;
const CHECKOUT_WORKSPACE_CENTER = 288;
const CHECKOUT_TRAY_IMAGES = {
  white: assetUrl('workspace/tray-yustream-white-transparent-user-20260701.webp'),
  warm: assetUrl('workspace/tray-yustream-transparent-user-20260701-v6.webp'),
  black: assetUrl('workspace/tray-yustream-black-transparent-user-20260701.webp')
};
const DEFAULT_CHECKOUT_DESIGN_TITLE = '\u6e29\u67d4\u5b88\u62a4 \u00b7 \u548c\u8c10\u5e73\u8861\u6b3e';
const DESIGN_NAME_MODAL_HINT_KEYWORD = '\u7ed9\u8fd9\u6761\u624b\u4e32\u8d77\u4e2a\u540d\u5b57';

function firstImageUrl(entry = {}) {
  const urls = (entry.image_urls || entry.image_pool || [])
    .concat(entry.image_url || [])
    .filter(Boolean);
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
  const x = placementCoordinate(placement, 'x', preferStringed);
  const y = placementCoordinate(placement, 'y', preferStringed);
  return Number.isFinite(x) && Number.isFinite(y);
}

function savedPlacementPoint(placement = {}, preferStringed = false) {
  const x = placementCoordinate(placement, 'x', preferStringed);
  const y = placementCoordinate(placement, 'y', preferStringed);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return {
    x: x + Number(placement.dx || 0),
    y: y + Number(placement.dy || 0)
  };
}

function solve3x3(matrix, vector) {
  const a = matrix.map(row => row.slice());
  const b = vector.slice();
  for (let col = 0; col < 3; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < 3; row += 1) {
      if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
    }
    if (Math.abs(a[pivot][col]) < 1e-6) return null;
    if (pivot !== col) {
      [a[pivot], a[col]] = [a[col], a[pivot]];
      [b[pivot], b[col]] = [b[col], b[pivot]];
    }
    const divisor = a[col][col];
    for (let item = col; item < 3; item += 1) a[col][item] /= divisor;
    b[col] /= divisor;
    for (let row = 0; row < 3; row += 1) {
      if (row === col) continue;
      const factor = a[row][col];
      for (let item = col; item < 3; item += 1) a[row][item] -= factor * a[col][item];
      b[row] -= factor * b[col];
    }
  }
  return b;
}

function fitPlacementCircle(points = []) {
  if (points.length < 3) return null;
  const sums = points.reduce((acc, point) => {
    const x = point.x;
    const y = point.y;
    const z = x * x + y * y;
    acc.x += x;
    acc.y += y;
    acc.xx += x * x;
    acc.yy += y * y;
    acc.xy += x * y;
    acc.z += z;
    acc.xz += x * z;
    acc.yz += y * z;
    return acc;
  }, { x: 0, y: 0, xx: 0, yy: 0, xy: 0, z: 0, xz: 0, yz: 0 });
  const solution = solve3x3([
    [sums.xx, sums.xy, sums.x],
    [sums.xy, sums.yy, sums.y],
    [sums.x, sums.y, points.length]
  ], [-sums.xz, -sums.yz, -sums.z]);
  if (!solution) return null;
  const centerX = -solution[0] / 2;
  const centerY = -solution[1] / 2;
  const radius = points.reduce((sum, point) => (
    sum + Math.sqrt((point.x - centerX) ** 2 + (point.y - centerY) ** 2)
  ), 0) / points.length;
  if (!Number.isFinite(centerX) || !Number.isFinite(centerY) || !Number.isFinite(radius)) return null;
  if (centerX < 180 || centerX > 480 || centerY < 180 || centerY > 480 || radius < 24 || radius > 320) return null;
  return { x: centerX, y: centerY, scaleBase: (centerX + centerY) / 2 };
}

function inferPreviewSourceOrigin(placements = [], design = {}) {
  const preferStringed = design.isLooseMode === false;
  const points = placements.map(item => savedPlacementPoint(item, preferStringed)).filter(Boolean);
  const fitted = fitPlacementCircle(points);
  if (fitted) return fitted;
  if (points.length) {
    const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
    const y = points.reduce((sum, point) => sum + point.y, 0) / points.length;
    const scaleBase = (x + y) / 2;
    if (Number.isFinite(scaleBase) && scaleBase >= 180 && scaleBase <= 480) {
      return { x, y, scaleBase };
    }
  }
  const storedCenter = Number(design.workspaceStageCenter || design.previewSourceCenter || design.preview_source_center);
  if (Number.isFinite(storedCenter) && storedCenter >= 180 && storedCenter <= 480) {
    return { x: storedCenter, y: storedCenter, scaleBase: storedCenter };
  }
  return {
    x: CHECKOUT_WORKSPACE_CENTER,
    y: CHECKOUT_WORKSPACE_CENTER,
    scaleBase: CHECKOUT_WORKSPACE_CENTER
  };
}

function moneyValue(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === '') continue;
    const amount = Number(value);
    if (Number.isFinite(amount)) return amount;
  }
  return 0;
}

function cleanDesignTitle(value = '') {
  const text = String(value || '').trim();
  if (!text || text.includes(DESIGN_NAME_MODAL_HINT_KEYWORD)) return '';
  return text;
}

function isInternalMaterialId(value) {
  const text = String(value || '').trim();
  return /^(mat|real)[_-]/i.test(text) || /^\d{10,}$/.test(text);
}

function cleanMaterialLabel(value) {
  const text = String(value || '').trim();
  if (!text || text === '-' || text === 'NaN') return '';
  if (isInternalMaterialId(text)) return '';
  if (/\u672a\u547d\u540d/.test(text)) return '';
  return text;
}

function fallbackMaterialLabel(entry = {}) {
  const typeText = [
    entry.top,
    entry.item_type,
    entry.type,
    entry.category,
    entry.series
  ].map(value => String(value || '')).join(' ');
  if (/accessory|spacer|pendant|charm|fitting|flower|托|配饰|吊坠|隔片/.test(typeText)) {
    return '\u5b9a\u5236\u914d\u9970';
  }
  return '\u5b9a\u5236\u73e0\u6750';
}

function sequenceDisplayName(entry = {}, key = '', fallbackName = '') {
  const candidates = [
    entry.name,
    entry.material_name,
    entry.materialName,
    entry.series,
    entry.category,
    fallbackName,
    key
  ];
  for (let index = 0; index < candidates.length; index += 1) {
    const name = cleanMaterialLabel(candidates[index]);
    if (name) return name;
  }
  return fallbackMaterialLabel(entry);
}

function normalizeSequenceItem(entry = {}, index = 0) {
  const key = entry.id || entry.sku || entry.material_id || '';
  const fallback = MATERIALS[key] || {};
  const imageUrls = (entry.image_urls || entry.image_pool || [])
    .concat(entry.image_url || [])
    .filter(Boolean);
  const size = entry.size || entry.diameter || '';
  const name = sequenceDisplayName(entry, key, fallback.name);
  const category = entry.category || entry.series || '';
  return {
    ...entry,
    index: Number(entry.index || index + 1),
    id: entry.id || key,
    sku: entry.sku || fallback.sku || key,
    name,
    category,
    series: entry.series || '',
    size,
    sizeText: size ? `${size}mm` : '',
    subText: [size ? `${size}mm` : '', category].filter(Boolean).join(' · '),
    price: moneyValue(entry.price, entry.priceText, entry.amount, fallback.price),
    weight: Number(entry.weight || 0),
    color: entry.color || '',
    shine: entry.shine || '',
    image_url: entry.image_url || imageUrls[0] || '',
    image_urls: imageUrls
  };
}

Page({
  data: {
    design: null,
    sequence: [],
    bom: [],
    trayPreviewImage: CHECKOUT_TRAY_IMAGES.warm,
    trayPreviewTheme: 'warm',
    trayPreviewImageFailed: false,
    amountText: '0.00',
    receiver: {
      name: '',
      phone: '',
      region: [],
      regionText: '',
      detailAddress: '',
      address: ''
    },
    fullAddress: '',
    hasAddress: false,
    addressError: '',
    remark: '',
    submitting: false,
    pageLoading: true
  },

  onLoad() {
    this.loadTrayPreviewImage();
    this.loadDesign();
    this.loadReceiver();
  },

  onReady() {
    wx.hideLoading();
  },

  loadTrayPreviewImage() {
    const design = wx.getStorageSync('currentDesign') || {};
    const storedTheme = wx.getStorageSync(TRAY_THEME_STORAGE_KEY);
    const trayTheme = design.trayTheme || design.tray_theme || storedTheme || 'white';
    const trayImage = design.trayImageUrl
      || design.tray_image_url
      || CHECKOUT_TRAY_IMAGES[trayTheme]
      || CHECKOUT_TRAY_IMAGES.white;
    this.setData({
      trayPreviewImage: trayImage,
      trayPreviewTheme: trayTheme,
      trayPreviewImageFailed: false
    });
  },

  loadReceiver() {
    const user = auth.getStoredUser();
    const cached = wx.getStorageSync(ADDRESS_KEY) || {};
    const receiver = {
      name: cached.name || '',
      phone: cached.phone || (user && user.phone_number) || '',
      region: cached.region || [],
      regionText: cached.regionText || '',
      detailAddress: cached.detailAddress || '',
      address: cached.address || ''
    };
    this.setReceiver(receiver);
  },

  loadDesign() {
    const design = wx.getStorageSync('currentDesign');
    const hasSelected = Array.isArray(design && design.selected) && design.selected.length;
    const hasSequence = Array.isArray(design && design.sequence) && design.sequence.length;
    if (!design || (!hasSelected && !hasSequence)) {
      this.setData({ pageLoading: false });
      return;
    }
    const rawSequence = hasSequence ? design.sequence : design.selected.map((id, index) => ({
      index: index + 1,
      id,
      name: MATERIALS[id] ? MATERIALS[id].name : id,
      sku: MATERIALS[id] ? MATERIALS[id].sku : id,
      price: MATERIALS[id] ? MATERIALS[id].price : 0
    }));
    const sequence = rawSequence.map(normalizeSequenceItem);
    this.applyDesignState(design, sequence);
    this.refreshDesignPrices();
  },

  buildBom(sequence = []) {
    const bomMap = {};
    sequence.forEach(item => {
      const key = item.sku || item.id || `${item.name}-${item.size}`;
      if (!bomMap[key]) {
        bomMap[key] = {
          sku: key,
          name: item.name,
          qty: 0,
          size: item.size || '',
          sizeText: item.sizeText || '',
          subText: item.subText || item.category || '',
          category: item.category || '',
          price: Number(item.price || 0),
          image_url: item.image_url || ''
        };
      }
      bomMap[key].qty += 1;
      bomMap[key].total = Number((bomMap[key].qty * bomMap[key].price).toFixed(2));
      bomMap[key].priceText = this.formatAmount(bomMap[key].price);
      bomMap[key].totalText = this.formatAmount(bomMap[key].total);
    });
    return Object.values(bomMap);
  },

  applyDesignState(design, sequence) {
    const bom = this.buildBom(sequence);
    const fallbackAmount = sequence.reduce((sum, item) => sum + Number(item.price || 0), 0);
    const summaryAmount = Number(design.summary && (design.summary.priceText || design.summary.price));
    const amount = Number.isFinite(summaryAmount) && summaryAmount > 0 ? summaryAmount : fallbackAmount;
    const summary = {
      ...(design.summary || {}),
      count: sequence.length,
      price: amount,
      priceText: this.formatAmount(amount),
      effectiveWrist: effectiveWristText(design.summary || {})
    };
    const displayTitle = cleanDesignTitle(design.name) || cleanDesignTitle(design.title) || DEFAULT_CHECKOUT_DESIGN_TITLE;
    const designForView = { ...design, summary, displayTitle };
    this.setData({
      design: designForView,
      sequence,
      bom,
      amountText: this.formatAmount(amount),
      pageLoading: false
    });
  },

  onTrayPreviewImageError() {
    this.setData({ trayPreviewImageFailed: true });
  },

  async refreshDesignPrices() {
    const design = this.data.design;
    const sequence = this.data.sequence || [];
    if (!design || !sequence.length) return;
    try {
      const payload = await getMaterials({ silent: true, timeout: 8000 });
      const materials = payload.materials || [];
      if (!materials.length) return;
      const byId = {};
      const bySku = {};
      materials.forEach(material => {
        const sku = material.sku || {};
        const visual = material.visual || {};
        const energy = material.energy || {};
        const normalized = {
          ...material,
          id: sku.id || material.id,
          skuId: sku.sku_id || material.skuId || material.sku_id,
          name: sku.name || material.name,
          category: sku.category || material.category,
          series: sku.series || material.series,
          grade: sku.grade || material.grade,
          effect: (energy.effects || []).join(' / ') || material.effect,
          element: energy.primary_element || material.element,
          size: sku.size_mm || material.size,
          price: sku.price_per_bead || material.price,
          weight: sku.weight_g || material.weight,
          image_url: visual.thumbnail_url || material.image_url,
          image_urls: visual.image_urls || material.image_urls || material.image_pool || []
        };
        if (normalized.id) byId[String(normalized.id)] = normalized;
        if (normalized.skuId) bySku[String(normalized.skuId)] = normalized;
      });

      const changed = [];
      const refreshed = sequence.map((item, index) => {
        const material = byId[String(item.id || item.material_id || '')]
          || bySku[String(item.sku || item.skuId || '')];
        if (!material) return item;
        const currentPrice = moneyValue(material.price, material.priceText, material.amount);
        const oldPrice = moneyValue(item.price, item.priceText);
        const hasReliableSnapshot = Boolean(item.snapshot_at);
        if (hasReliableSnapshot && oldPrice !== currentPrice) {
          changed.push(`${material.name || item.name || '珠材'} ¥${this.formatAmount(oldPrice)}→¥${this.formatAmount(currentPrice)}`);
        }
        return normalizeSequenceItem({
          ...item,
          id: material.id || item.id,
          material_id: material.id || item.material_id,
          sku: material.skuId || material.sku || item.sku,
          skuId: material.skuId || item.skuId || item.sku,
          name: material.name || item.name,
          category: material.category || item.category,
          series: material.series || item.series,
          grade: material.grade || item.grade,
          effect: material.effect || item.effect,
          element: material.element || item.element,
          size: material.size || item.size,
          diameter: material.size || item.diameter,
          price: currentPrice,
          weight: material.weight || item.weight,
          color: material.color || item.color,
          shine: material.shine || item.shine,
          image_url: item.image_url || material.image_url || firstImageUrl(material),
          image_urls: material.image_urls || material.image_pool || item.image_urls || [],
          snapshot_at: item.snapshot_at || new Date().toISOString()
        }, index);
      });

      const refreshedAmount = refreshed.reduce((sum, item) => sum + Number(item.price || 0), 0);
      const nextDesign = {
        ...design,
        summary: {
          ...(design.summary || {}),
          count: refreshed.length,
          price: refreshedAmount,
          priceText: this.formatAmount(refreshedAmount)
        },
        sequence: refreshed,
        selected: refreshed.map(item => item.id || item.sku).filter(Boolean)
      };
      this.applyDesignState(nextDesign, refreshed);
      wx.setStorageSync('currentDesign', {
        ...nextDesign,
        summary: this.data.design.summary
      });
      if (changed.length) {
        wx.showModal({
          title: '珠材价格已同步',
          content: `当前方案已按最新珠材价格刷新：${changed.slice(0, 3).join('；')}${changed.length > 3 ? '…' : ''}`,
          showCancel: false,
          confirmText: '知道了'
        });
      }
    } catch (error) {
      console.warn('refresh checkout material prices failed:', error.message || error);
    }
  },

  buildPreviewBeads(sequence, placements = [], design = {}) {
    const beads = (sequence || []).slice(0, 40);
    const count = Math.max(beads.length, 1);
    const sourceOrigin = inferPreviewSourceOrigin(placements, design);
    const placementScale = CHECKOUT_PREVIEW_CENTER / sourceOrigin.scaleBase;
    const preferStringed = design.isLooseMode === false;
    const useSavedPlacements = placements.some(item => hasSavedPlacement(item, preferStringed));
    const initialBeadSizes = beads.map((item, index) => (
      this.resolvePreviewBeadSize(item, placements[index] || item.placement || {}, count)
    ));
    const ring = this.buildPreviewRingGeometry(beads, design, initialBeadSizes);

    return beads.map((item, index) => {
      const placement = placements[index] || item.placement || {};
      const savedX = placementCoordinate(placement, 'x', preferStringed) + Number(placement.dx || 0);
      const savedY = placementCoordinate(placement, 'y', preferStringed) + Number(placement.dy || 0);
      const hasSavedPosition = useSavedPlacements && Number.isFinite(savedX) && Number.isFinite(savedY);
      const beadSize = hasSavedPosition
        ? Math.max(30, Math.min(62, (initialBeadSizes[index] || 52) * placementScale))
        : (ring.beadSizes[index] || initialBeadSizes[index] || 52);
      const ringPoint = ring.points[index] || {
        x: CHECKOUT_PREVIEW_CENTER,
        y: CHECKOUT_PREVIEW_CENTER,
        angle: 0
      };
      const x = hasSavedPosition
        ? CHECKOUT_PREVIEW_CENTER + (savedX - sourceOrigin.x) * placementScale
        : ringPoint.x;
      const y = hasSavedPosition
        ? CHECKOUT_PREVIEW_CENTER + (savedY - sourceOrigin.y) * placementScale
        : ringPoint.y;
      const rotation = hasSavedPosition ? Number(placement.rotation || 0) : ringPoint.angle;
      return {
        ...item,
        image_url: placement.image_url || item.image_url || firstImageUrl(item),
        style: `width:${beadSize}rpx;height:${beadSize}rpx;background:${this.buildPreviewBeadBackground(item)};transform:translate3d(${(x - beadSize / 2).toFixed(1)}rpx,${(y - beadSize / 2).toFixed(1)}rpx,0) rotate(${rotation.toFixed(1)}deg);`
      };
    });
  },

  resolvePreviewBeadSize(item = {}, placement = {}, count = 0) {
    const placementSize = Number(placement.beadSize || placement.diameter);
    const sizeMm = Number(item.size || item.diameter || 0);
    const rawSize = Number.isFinite(placementSize) && placementSize > 0
      ? placementSize
      : (sizeMm ? sizeMm * 5.4 : 52);
    const maxSize = count >= 28 ? 46 : count >= 22 ? 50 : 58;
    return Math.max(30, Math.min(maxSize, rawSize));
  },

  buildPreviewRingGeometry(beads = [], design = {}, beadSizes = []) {
    const count = Math.max(beads.length, 1);
    const wristSize = Number(design.wristSize || design.wrist_size || (design.summary && design.summary.wristSize) || 16);
    const safeWrist = Number.isFinite(wristSize) ? Math.max(10, Math.min(25, wristSize)) : 16;
    const wristRadius = Math.round(166 + ((safeWrist - 10) / 15) * 28);
    let sizes = beadSizes.length ? beadSizes.slice() : beads.map(() => 52);
    let radius = count >= 3
      ? Math.max(wristRadius, this.solvePreviewTangentRingRadius(sizes))
      : wristRadius;
    const largestRadius = Math.max(...sizes, 1) / 2;
    const maxOuterRadius = CHECKOUT_PREVIEW_CENTER - 30;
    if (radius + largestRadius > maxOuterRadius) {
      const scale = maxOuterRadius / (radius + largestRadius);
      sizes = sizes.map(size => Math.max(30, size * scale));
      radius = count >= 3
        ? Math.min(maxOuterRadius - Math.max(...sizes) / 2, this.solvePreviewTangentRingRadius(sizes))
        : Math.min(wristRadius, maxOuterRadius - Math.max(...sizes) / 2);
    }
    const points = beads.map((item, index) => {
      const angle = -90 + (360 / count) * index;
      const rad = angle * Math.PI / 180;
      return {
        x: CHECKOUT_PREVIEW_CENTER + Math.cos(rad) * radius,
        y: CHECKOUT_PREVIEW_CENTER + Math.sin(rad) * radius,
        angle
      };
    });
    return { points, beadSizes: sizes };
  },

  solvePreviewTangentRingRadius(beadSizes = []) {
    if (beadSizes.length < 3) return 156;
    const centerDistances = beadSizes.map((size, index) => {
      const nextSize = beadSizes[(index + 1) % beadSizes.length];
      return (size + nextSize) / 2 + 0.5;
    });
    let low = Math.max(...centerDistances) / 2 + 0.01;
    let high = Math.max(480, beadSizes.reduce((sum, size) => sum + size, 0));
    for (let iteration = 0; iteration < 40; iteration += 1) {
      const radius = (low + high) / 2;
      const angleSum = centerDistances.reduce((sum, distance) => {
        return sum + 2 * Math.asin(Math.min(1, distance / (2 * radius)));
      }, 0);
      if (angleSum > Math.PI * 2) low = radius;
      else high = radius;
    }
    return (low + high) / 2;
  },

  buildPreviewBeadBackground(item = {}) {
    return `radial-gradient(circle at 32% 28%, ${item.shine || '#fff'} 0 12%, ${item.color || '#d8d2c8'} 16% 60%, rgba(0,0,0,.20) 100%)`;
  },

  formatAmount(value) {
    const amount = Number(value || 0);
    return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
  },

  setReceiver(receiver) {
    const regionText = receiver.regionText || (receiver.region || []).join(' ');
    const fullAddress = [regionText, receiver.detailAddress].filter(Boolean).join(' ');
    this.setData({
      receiver: { ...receiver, regionText, address: fullAddress },
      fullAddress,
      hasAddress: !!(receiver.name && receiver.phone && fullAddress)
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    const receiver = { ...this.data.receiver, [field]: e.detail.value };
    this.setReceiver(receiver);
    if (this.data.addressError) this.setData({ addressError: '' });
  },

  onRegionChange(e) {
    const region = e.detail.value || [];
    this.setReceiver({
      ...this.data.receiver,
      region,
      regionText: region.join(' ')
    });
    if (this.data.addressError) this.setData({ addressError: '' });
  },

  onRemarkInput(e) {
    this.setData({ remark: e.detail.value || '' });
  },

  chooseWechatAddress() {
    wx.chooseAddress({
      success: res => {
        const region = [res.provinceName, res.cityName, res.countyName].filter(Boolean);
        this.setReceiver({
          name: res.userName || '',
          phone: res.telNumber || '',
          region,
          regionText: region.join(' '),
          detailAddress: res.detailInfo || '',
          address: ''
        });
        wx.showToast({ title: '地址已导入', icon: 'success' });
      },
      fail: err => {
        console.warn('chooseAddress failed:', err);
        wx.showToast({ title: '可手动填写地址', icon: 'none' });
      }
    });
  },

  focusAddressForm() {
    wx.pageScrollTo({ selector: '#addressForm', duration: 250 });
  },

  validateReceiver() {
    const receiver = this.data.receiver;
    if (!receiver.name || receiver.name.trim().length < 2) return '请填写至少 2 个字的收货人姓名';
    if (!/^1\d{10}$/.test(receiver.phone || '')) return '请填写正确的 11 位手机号';
    if (!receiver.region || receiver.region.length < 3) return '请选择省 / 市 / 区';
    if (!receiver.detailAddress || receiver.detailAddress.trim().length < 5) return '请填写详细地址，至少 5 个字';
    return '';
  },

  async submitOrder() {
    if (this.data.submitting) return;
    let user;
    try {
      user = await auth.requireLogin('登录后才能提交订单和查看履约进度。');
    } catch (error) {
      return;
    }
    if (!this.data.design) {
      wx.showToast({ title: '暂无可提交设计', icon: 'none' });
      return;
    }
    const error = this.validateReceiver();
    if (error) {
      this.setData({ addressError: error });
      wx.showToast({ title: error, icon: 'none' });
      this.focusAddressForm();
      return;
    }

    const receiver = {
      name: this.data.receiver.name.trim(),
      phone: this.data.receiver.phone,
      region: this.data.receiver.region,
      detailAddress: this.data.receiver.detailAddress.trim(),
      address: this.data.fullAddress
    };
    wx.setStorageSync(ADDRESS_KEY, receiver);

    this.setData({ submitting: true });
    wx.showLoading({ title: '生成订单' });
    try {
      const result = await createOrder({
        user_id: user.user_id,
        design_id: this.data.design.designId || this.data.design.design_id || '',
        receiver,
        remark: (this.data.remark || '').trim(),
        design: this.data.design,
        sequence: this.data.sequence,
        bom: this.data.bom
      });
      this.cacheOrder(result.order);
      wx.hideLoading();

      const payment = result.payment || {};
      if (payment.available && payment.pay_params) {
        await this.requestWechatPayment(payment.pay_params);
        wx.showToast({ title: '支付完成', icon: 'success' });
        this.goSuccess(result.order.order_id);
        return;
      }

      wx.showModal({
        title: '订单已生成',
        content: `${payment.message || '订单已保存为待付款。'}${env.isLocalApi ? '\n\n本地调试可先模拟支付成功，继续测试后续流程。' : ''}`,
        confirmText: env.isLocalApi ? '模拟支付' : '查看订单',
        cancelText: '稍后',
        showCancel: true,
        success: async (res) => {
          if (res.confirm && env.isLocalApi) {
            await this.mockPay(result.order.order_id, user.user_id);
            return;
          }
          this.goOrderDetail(result.order.order_id);
        }
      });
    } catch (error) {
      wx.hideLoading();
      console.error('submit order failed:', error);
      this.handleSubmitError(error);
    } finally {
      this.setData({ submitting: false });
    }
  },

  handleSubmitError(error) {
    const message = error && error.message ? error.message : '下单失败';
    if (message.includes('珠材价格已更新') || message.includes('已下架或无库存')) {
      wx.showModal({
        title: '珠材信息已更新',
        content: message,
        confirmText: '返回工作台',
        cancelText: '稍后',
        success: (res) => {
          if (res.confirm) {
            wx.navigateBack({
              fail: () => wx.redirectTo({ url: '/pages/workspace/workspace' })
            });
          }
        }
      });
      return;
    }
    wx.showToast({ title: message, icon: 'none' });
  },

  async mockPay(orderId, userId) {
    wx.showLoading({ title: '模拟支付' });
    try {
      const order = await mockPayOrder(orderId, userId);
      this.cacheOrder(order);
      wx.hideLoading();
      wx.showToast({ title: '已进入待发货', icon: 'success' });
      this.goSuccess(order.order_id || orderId);
    } catch (error) {
      wx.hideLoading();
      wx.showToast({ title: error.message || '模拟支付失败', icon: 'none' });
    }
  },

  requestWechatPayment(payParams) {
    return new Promise((resolve, reject) => {
      wx.requestPayment({ ...payParams, success: resolve, fail: reject });
    });
  },

  cacheOrder(order) {
    const orders = wx.getStorageSync('orders') || [];
    const localOrder = {
      id: order.order_id,
      userId: order.user_id,
      createdAt: order.created_at,
      receiver: order.receiver,
      design: order.design,
      sequence: order.sequence,
      bom: order.bom,
      rawStatus: order.status,
      paymentStatus: order.payment_status,
      statusKey: this.statusKey(order),
      status: order.status_text || this.statusText(order),
      totalAmount: order.total_amount,
      remark: order.remark || '',
      logistics: order.logistics || {},
      statusHistory: order.status_history || []
    };
    wx.setStorageSync('orders', [localOrder, ...orders.filter(item => item.id !== localOrder.id)]);
  },

  goSuccess(orderId) {
    wx.navigateTo({ url: `/pages/order-success/order-success?id=${encodeURIComponent(orderId || '')}` });
  },

  goOrderDetail(orderId) {
    wx.redirectTo({ url: `/pages/order-detail/order-detail?id=${encodeURIComponent(orderId || '')}` });
  },

  statusKey(order) {
    if (order.status === 'pending_ship') return 'ship';
    if (order.status === 'shipped') return 'receive';
    if (order.status === 'after_sale' || order.status === 'refund_requested' || order.status === 'refunded') return 'after';
    if (order.payment_status === 'unpaid' || order.status === 'pending_payment') return 'pay';
    return 'done';
  },

  statusText(order) {
    return {
      pending_payment: '待付款',
      pending_ship: '待发货',
      shipped: '待收货',
      completed: '已完成',
      after_sale: '售后中',
      refund_requested: '退款中',
      refunded: '已退款'
    }[order.status] || (order.payment_status === 'paid' ? '已支付' : '待付款');
  },

  goBack() {
    wx.navigateBack();
  }
});
