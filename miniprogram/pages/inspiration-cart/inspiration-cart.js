const { assetUrl } = require('../../utils/assets');
const auth = require('../../utils/auth');
const { getCartItems, updateCartItem, deleteCartItem } = require('../../utils/api');

const CART_KEY = 'diyDesignCart';

const MATERIAL_NAMES = {
  clearQuartz8: '白水晶',
  clearQuartz10: '白水晶',
  clearQuartz12: '白水晶',
  clearQuartz14: '白水晶',
  amethyst8: '乌拉圭紫水晶',
  amethyst10: '乌拉圭紫水晶',
  citrine8: '巴西黄水晶',
  citrine10: '巴西黄水晶',
  obsidian10: '冰种黑曜石',
  tigerEye8: '南非虎眼石',
  moonstone6: '雪花幽灵',
  moonstone8: '雪花幽灵',
  aquamarine8: '巴西海蓝宝',
  blueRutilatedQuartz10: '蓝发晶',
  garnet8: '石榴石',
  turquoise6: '绿松石',
  greenPhantom8: '绿幽灵',
  smokyQuartz8: '茶晶',
  hematite8: '赤铁矿',
  roseQuartz8: '马达加斯加粉晶',
  silverSpacer: '925 银隔片',
  goldSpacer: '鎏金隔片',
  foxPendant: '粉晶狐狸吊坠'
};

const MATERIAL_ASSETS = {
  aquamarine8: assetUrl('home/aquamarine.webp'),
  amethyst8: assetUrl('home/amethyst.webp'),
  amethyst10: assetUrl('home/amethyst.webp'),
  clearQuartz8: assetUrl('home/clear-quartz.webp'),
  clearQuartz10: assetUrl('home/clear-quartz.webp'),
  clearQuartz12: assetUrl('home/clear-quartz.webp'),
  clearQuartz14: assetUrl('home/clear-quartz.webp'),
  moonstone6: assetUrl('home/moonstone.webp'),
  moonstone8: assetUrl('home/moonstone.webp'),
  citrine8: assetUrl('home/citrine.webp'),
  citrine10: assetUrl('home/citrine.webp'),
  roseQuartz8: assetUrl('home/moonstone.webp'),
  obsidian10: assetUrl('home/amethyst.webp')
};

const MINI_PREVIEW_STAGE_SIZE = 360;
const MINI_PREVIEW_CENTER = MINI_PREVIEW_STAGE_SIZE / 2;
const WORKSPACE_PREVIEW_CENTER = 288;
const CART_TRAY_IMAGE_URL = assetUrl('workspace/tray-yustream-transparent-user-20260701-v6.webp');
const CART_ACTION_ICONS = {
  workbench: assetUrl('cart/cart-workbench.png'),
  remove: assetUrl('cart/cart-delete.png')
};
const DEFAULT_CART_PLAN_NAME = 'Yustream DIY 手串方案';
const DESIGN_NAME_MODAL_HINT_KEYWORD = '给这条手串起个名字';

const MATERIAL_CODE_LABELS = [
  { pattern: /colorful[_-]?phantom/, label: '彩幽灵' },
  { pattern: /green[_-]?phantom/, label: '绿幽灵' },
  { pattern: /red[_-]?phantom/, label: '红幽灵' },
  { pattern: /starry|mantianxing|full[_-]?star/, label: '满天星' },
  { pattern: /clear[_-]?quartz/, label: '白水晶' },
  { pattern: /rose[_-]?quartz/, label: '粉晶' },
  { pattern: /smoky[_-]?quartz/, label: '茶晶' },
  { pattern: /citrine/, label: '黄水晶' },
  { pattern: /amethyst/, label: '紫水晶' },
  { pattern: /aquamarine/, label: '海蓝宝' },
  { pattern: /obsidian/, label: '黑曜石' },
  { pattern: /tiger[_-]?eye/, label: '虎眼石' },
  { pattern: /moonstone/, label: '月光石' },
  { pattern: /garnet/, label: '石榴石' },
  { pattern: /turquoise/, label: '绿松石' },
  { pattern: /hematite/, label: '赤铁矿' }
];

function toMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
}

function clampQty(value) {
  const qty = Math.floor(Number(value || 1));
  return Math.min(99, Math.max(1, qty));
}

function cleanPlanName(value = '') {
  const text = String(value || '').trim();
  if (!text || text.includes(DESIGN_NAME_MODAL_HINT_KEYWORD)) return '';
  return text;
}

function formatCreatedTime(value) {
  if (!value) return '';
  let date = null;
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 0) {
    const timestamp = numeric < 100000000000 ? numeric * 1000 : numeric;
    date = new Date(timestamp);
  } else {
    const text = String(value || '').trim();
    const matched = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/);
    if (matched) {
      date = new Date(
        Number(matched[1]),
        Number(matched[2]) - 1,
        Number(matched[3]),
        Number(matched[4] || 0),
        Number(matched[5] || 0),
        Number(matched[6] || 0)
      );
    } else {
      date = new Date(text);
    }
  }
  if (!date || Number.isNaN(date.getTime())) return '';
  const year = `${date.getFullYear()}`;
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  const second = `${date.getSeconds()}`.padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

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

function inferPlacementSourceOrigin(placements = [], source = {}) {
  const preferStringed = source.isLooseMode === false;
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
  const storedCenter = Number(source.workspaceStageCenter || source.previewSourceCenter || source.preview_source_center);
  if (Number.isFinite(storedCenter) && storedCenter >= 180 && storedCenter <= 480) {
    return { x: storedCenter, y: storedCenter, scaleBase: storedCenter };
  }
  return { x: WORKSPACE_PREVIEW_CENTER, y: WORKSPACE_PREVIEW_CENTER, scaleBase: WORKSPACE_PREVIEW_CENTER };
}

function hasSavedPlacement(placement = {}, preferStringed = false) {
  const x = placementCoordinate(placement, 'x', preferStringed);
  const y = placementCoordinate(placement, 'y', preferStringed);
  return Number.isFinite(x) && Number.isFinite(y);
}

function hasChinese(value = '') {
  return /[\u4e00-\u9fff]/.test(String(value || ''));
}

function codeDisplayName(value = '') {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (hasChinese(raw)) return raw;
  const normalized = raw
    .replace(/^bead[_-]/i, '')
    .replace(/[_-]?bead$/i, '')
    .toLowerCase();
  const match = MATERIAL_CODE_LABELS.find(item => item.pattern.test(normalized));
  if (!match) return '';
  const sizeMatch = normalized.match(/(\d+(?:\.\d+)?)\s*mm/);
  return `${match.label}${sizeMatch ? ` ${sizeMatch[1]}mm` : ''}`;
}

function displayMaterialName(entry = {}) {
  const key = entry.id || entry.sku || entry.material_id || '';
  const candidates = [
    entry.name,
    entry.display_name,
    entry.material_name,
    entry.series,
    entry.category,
    MATERIAL_NAMES[key],
    codeDisplayName(key)
  ];
  for (let index = 0; index < candidates.length; index += 1) {
    const name = String(candidates[index] || '').trim();
    if (!name) continue;
    if (hasChinese(name)) return name;
    const fromCode = codeDisplayName(name);
    if (fromCode) return fromCode;
  }
  return '';
}

function fallbackName(entry = {}) {
  return displayMaterialName(entry) || '定制珠材';
}

function buildSequence(item = {}) {
  if (Array.isArray(item.sequence) && item.sequence.length) {
    return item.sequence.map((entry, index) => {
      const imageUrls = (entry.image_urls || entry.image_pool || [])
        .concat(entry.image_url || [])
        .filter(Boolean);
      const size = entry.size || entry.diameter || '';
      return {
        ...entry,
        index: Number(entry.index || index + 1),
        id: entry.id || entry.sku || entry.material_id || '',
        sku: entry.sku || entry.id || entry.material_id || '',
        name: fallbackName(entry),
        category: entry.category || '',
        series: entry.series || '',
        size,
        sizeText: size ? `${size}mm` : '',
        price: Number(entry.price || 0),
        weight: Number(entry.weight || 0),
        image_url: entry.image_url || imageUrls[0] || '',
        image_urls: imageUrls
      };
    });
  }
  return (item.selected || []).map((id, index) => ({
    index: index + 1,
    id,
    sku: id,
    name: displayMaterialName({ id, sku: id }) || '定制珠材',
    size: '',
    sizeText: '',
    price: 0,
    image_url: ''
  }));
}

function createMiniBeads(sequence = [], count = 12, radius = 38, size = 24, placements = [], source = {}) {
  const safeSequence = sequence.length ? sequence : [{ id: 'clearQuartz8' }];
  const displayCount = Math.max(1, Math.min(count, safeSequence.length || count, 24));
  const center = MINI_PREVIEW_CENTER;
  const preferStringed = source.isLooseMode === false;
  const hasPlacementLayout = placements.some(item => hasSavedPlacement(item, preferStringed));
  const sourceOrigin = inferPlacementSourceOrigin(placements, source);
  const placementScale = center / sourceOrigin.scaleBase;
  return Array.from({ length: displayCount }, (_, index) => {
    const bead = safeSequence[index % safeSequence.length] || {};
    const placement = placements[index] || {};
    const beadMm = Number(bead.size || bead.diameter || 0);
    const placementSize = Number(placement.beadSize || placement.diameter || placement.size);
    const beadSize = hasPlacementLayout
      ? Math.max(18, Math.min(48, (Number.isFinite(placementSize) && placementSize > 0 ? placementSize : (beadMm ? beadMm * 5.4 : size)) * placementScale))
      : Math.max(22, Math.min(40, Number(placement.beadSize) || (beadMm ? beadMm * 3.25 : size)));
    let x;
    let y;
    let angle;
    if (hasPlacementLayout && hasSavedPlacement(placement, preferStringed)) {
      const savedX = placementCoordinate(placement, 'x', preferStringed) + Number(placement.dx || 0);
      const savedY = placementCoordinate(placement, 'y', preferStringed) + Number(placement.dy || 0);
      x = center + (savedX - sourceOrigin.x) * placementScale;
      y = center + (savedY - sourceOrigin.y) * placementScale;
      angle = Number(placement.rotation || 0);
    } else {
      const ringRadius = Math.max(62, Math.min(118, radius + displayCount * 2.2));
      angle = -90 + (360 / displayCount) * index;
      const rad = angle * Math.PI / 180;
      x = center + Math.cos(rad) * ringRadius;
      y = center + Math.sin(rad) * ringRadius;
    }
    const code = bead.id || bead.sku || 'clearQuartz8';
    return {
      src: placement.image_url || bead.image_url || firstImageUrl(bead) || MATERIAL_ASSETS[code] || MATERIAL_ASSETS.clearQuartz8,
      style: `left:${(x - beadSize / 2).toFixed(1)}rpx;top:${(y - beadSize / 2).toFixed(1)}rpx;width:${beadSize.toFixed(1)}rpx;height:${beadSize.toFixed(1)}rpx;transform:rotate(${angle.toFixed(1)}deg);`
    };
  });
}

function buildRecipeText(sequence = []) {
  const names = [];
  sequence.forEach(entry => {
    const name = displayMaterialName(entry);
    if (name && !names.includes(name)) names.push(name);
  });
  if (!names.length) return `${sequence.length || 0} 颗定制珠材`;
  return names.slice(0, 4).join(' · ') + (names.length > 4 ? ` 等 ${names.length} 种` : '');
}

function isPreviewImageUrl(url = '') {
  return /\/designs\/previews\/|preview/i.test(String(url || ''));
}

function resolvePreviewImage(item = {}) {
  const candidates = [
    item.preview_image,
    item.previewImage,
    item.preview_url,
    item.previewUrl,
    item.design_preview_url,
    item.designPreviewUrl
  ].filter(Boolean);
  if (candidates.length) return candidates[0];
  return isPreviewImageUrl(item.image_url) ? item.image_url : '';
}

function normalizeCartItem(item = {}, index = 0) {
  const sequence = buildSequence(item);
  const summary = item.summary || {};
  const key = item.key || item.cart_item_id || item.id || `cart-${item.createdAt || Date.now()}-${index}`;
  const count = Number(summary.count || item.count || sequence.length || (item.selected || []).length || 0);
  const price = Number(summary.priceText || summary.price || item.price || item.amount || 0);
  const qty = clampQty(item.qty || item.quantity || 1);
  const wristSize = item.wristSize || item.wrist_size || item.wrist || 16;
  const wearStyle = item.wearStyle === 'double' ? '双圈' : '单圈';
  const previewImage = resolvePreviewImage(item);
  const createdAt = item.createdAt || item.created_at || item.createdAtMs || item.created_at_ms || '';
  const planName = cleanPlanName(item.name)
    || cleanPlanName(item.title)
    || cleanPlanName(item.summary && item.summary.name)
    || `${DEFAULT_CART_PLAN_NAME} ${index + 1}`;

  return {
    ...item,
    key,
    id: item.id || key,
    materialIds: item.materialIds || item.selected || sequence.map(entry => entry.id || entry.sku),
    name: planName,
    title: item.title || planName,
    planName,
    desc: item.desc || `${count} 颗 · ${wearStyle}`,
    wristSize,
    wearStyle: item.wearStyle || 'single',
    tone: item.tone || 'clear',
    imageUrl: previewImage,
    preview_image: previewImage,
    previewImage,
    createdAt,
    created_at: item.created_at || createdAt,
    createdTime: formatCreatedTime(createdAt),
    sequence,
    recipeText: item.recipeText || buildRecipeText(sequence),
    miniBeads: createMiniBeads(sequence, Math.max(1, Math.min(sequence.length || 12, 24)), 40, 24, item.placements || [], item),
    price,
    priceText: toMoney(price),
    qty,
    lineTotal: Number((price * qty).toFixed(2)),
    lineTotalText: toMoney(price * qty)
  };
}

Page({
  data: {
    items: [],
    trayImageUrl: CART_TRAY_IMAGE_URL,
    cartActionIcons: CART_ACTION_ICONS,
    manageMode: false,
    checkoutLoadingKey: '',
    checkoutActionText: '\u53bb\u7ed3\u7b97',
    checkoutLoadingText: '\u6b63\u5728\u8fdb\u5165\u786e\u8ba4\u8ba2\u5355'
  },

  onLoad() {
    wx.redirectTo({ url: '/pages/my-plans/my-plans' });
  },

  onShow() {
    wx.hideLoading();
    if (this.data.checkoutLoadingKey) this.setData({ checkoutLoadingKey: '' });
    this.loadCart();
  },

  async loadCart() {
    let cart = wx.getStorageSync(CART_KEY) || [];
    try {
      const user = await auth.requireLogin('登录后才能查看购物车。');
      const rows = await getCartItems(user.user_id, { silent: true, timeout: 8000 });
      cart = rows
        .filter(row => (row.item_type || 'diy_design') === 'diy_design')
        .map(row => ({
          ...(row.item || {}),
          id: row.cart_item_id,
          key: row.cart_item_id,
          cart_item_id: row.cart_item_id,
          quantity: row.quantity,
          qty: row.quantity,
          created_at: row.created_at,
          updated_at: row.updated_at
        }));
      wx.setStorageSync(CART_KEY, cart);
    } catch (error) {
      console.warn('load cart fallback:', error.message || error);
    }
    this.applyItems(cart.map(normalizeCartItem));
  },

  applyItems(items) {
    const nextItems = items.map(item => ({
      ...item,
      lineTotal: Number((item.price * item.qty).toFixed(2)),
      lineTotalText: toMoney(item.price * item.qty)
    }));
    this.setData({ items: nextItems });
  },

  persistItems(items) {
    const stored = items.map(item => {
      const {
        selected,
        recipeText,
        miniBeads,
        priceText,
        lineTotal,
        lineTotalText,
        imageUrl,
        previewImage,
        createdTime,
        materialIds,
        ...rest
      } = item;
      return {
        ...rest,
        preview_image: item.imageUrl,
        previewImage: item.imageUrl,
        image_url: item.imageUrl,
        selected: materialIds || [],
        qty: clampQty(item.qty)
      };
    });
    wx.setStorageSync(CART_KEY, stored);
  },

  toggleManageMode() {
    this.setData({ manageMode: !this.data.manageMode });
  },

  async changeQty(e) {
    const key = e.currentTarget.dataset.key;
    const delta = Number(e.currentTarget.dataset.delta || 0);
    const items = this.data.items.map(item => (
      item.key === key ? { ...item, qty: clampQty(item.qty + delta) } : item
    ));
    const changed = items.find(item => item.key === key);
    if (changed && changed.cart_item_id) {
      try {
        const user = await auth.requireLogin('登录后才能更新购物车。');
        await updateCartItem(changed.cart_item_id, { user_id: user.user_id, quantity: changed.qty });
      } catch (error) {
        wx.showToast({ title: error.message || '更新购物车失败', icon: 'none' });
        return;
      }
    }
    this.persistItems(items);
    this.applyItems(items);
  },

  async removeItem(e) {
    const key = e.currentTarget.dataset.key;
    const current = this.data.items.find(item => item.key === key);
    if (current && current.cart_item_id) {
      try {
        const user = await auth.requireLogin('登录后才能更新购物车。');
        await deleteCartItem(current.cart_item_id, user.user_id);
      } catch (error) {
        wx.showToast({ title: error.message || '移出购物车失败', icon: 'none' });
        return;
      }
    }
    const items = this.data.items.filter(item => item.key !== key);
    this.persistItems(items);
    this.applyItems(items);
    wx.showToast({ title: '已移出购物车', icon: 'none' });
  },

  buildDesignPayload(item = {}) {
    return {
      cart_item_id: item.cart_item_id || item.key || item.id || '',
      cartItemId: item.cart_item_id || item.key || item.id || '',
      cartIdempotencyKey: item.cartIdempotencyKey || '',
      designId: item.designId || item.design_id || '',
      design_id: item.designId || item.design_id || '',
      name: item.name || item.planName || item.title || '',
      title: item.title || item.planName || item.name || '',
      userId: item.userId || '',
      selected: item.materialIds || item.sequence.map(entry => entry.id || entry.sku),
      placements: item.placements || [],
      wristSize: item.wristSize,
      wearStyle: item.wearStyle || 'single',
      isLooseMode: item.isLooseMode === true,
      sourceContext: item.sourceContext || null,
      preview_image: item.imageUrl || item.preview_image || item.previewImage || '',
      previewImage: item.imageUrl || item.preview_image || item.previewImage || '',
      image_url: item.imageUrl || item.preview_image || item.previewImage || '',
      summary: item.summary || {
        count: item.sequence.length,
        price: item.price,
        priceText: item.priceText
      },
      sequence: item.sequence
    };
  },

  findItemByEvent(e) {
    const key = e.currentTarget.dataset.key;
    return this.data.items.find(entry => entry.key === key);
  },

  editDesign(e) {
    const item = this.findItemByEvent(e);
    if (!item) return;
    wx.setStorageSync('currentDesign', this.buildDesignPayload(item));
    wx.setStorageSync('workspaceOpenDesign', 'cart');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  openDesign(e) {
    this.editDesign(e);
  },

  checkoutDesign(e) {
    const item = this.findItemByEvent(e);
    if (!item) return;
    wx.setStorageSync('currentDesign', this.buildDesignPayload(item));
    this.setData({ checkoutLoadingKey: item.key });
    wx.showLoading({ title: '\u6b63\u5728\u8fdb\u5165\u786e\u8ba4\u8ba2\u5355', mask: true });
    wx.navigateTo({
      url: '/pages/checkout/checkout',
      fail: () => {
        wx.hideLoading();
        this.setData({ checkoutLoadingKey: '' });
        wx.showToast({ title: '\u6253\u5f00\u786e\u8ba4\u8ba2\u5355\u5931\u8d25', icon: 'none' });
      }
    });
  },

  continueDiy() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goHome() {
    wx.switchTab({ url: '/pages/home/home' });
  }
});
