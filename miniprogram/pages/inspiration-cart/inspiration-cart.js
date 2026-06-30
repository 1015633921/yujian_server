const { assetUrl } = require('../../utils/assets');
const auth = require('../../utils/auth');
const { getCartItems, updateCartItem, deleteCartItem } = require('../../utils/api');

const CART_KEY = 'diyDesignCart';

const MATERIAL_NAMES = {
  clearQuartz8: '喜马拉雅白水晶',
  clearQuartz10: '喜马拉雅白水晶',
  clearQuartz12: '喜马拉雅白水晶',
  clearQuartz14: '喜马拉雅白水晶',
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

function firstImageUrl(entry = {}) {
  const urls = (entry.image_urls || entry.image_pool || [])
    .concat(entry.image_url || [])
    .filter(Boolean);
  return urls[0] || '';
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

function createMiniBeads(sequence = [], count = 12, radius = 38, size = 24, placements = []) {
  const safeSequence = sequence.length ? sequence : [{ id: 'clearQuartz8' }];
  const displayCount = Math.max(1, Math.min(count, safeSequence.length || count, 18));
  return Array.from({ length: displayCount }, (_, index) => {
    const angle = (360 / displayCount) * index;
    const bead = safeSequence[index % safeSequence.length] || {};
    const placement = placements[index] || {};
    const code = bead.id || bead.sku || 'clearQuartz8';
    return {
      src: placement.image_url || bead.image_url || firstImageUrl(bead) || MATERIAL_ASSETS[code] || MATERIAL_ASSETS.clearQuartz8,
      style: `width:${size}rpx;height:${size}rpx;transform:rotate(${angle}deg) translateY(-${radius}rpx) rotate(${-angle}deg);`
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

  return {
    ...item,
    key,
    id: item.id || key,
    materialIds: item.materialIds || item.selected || sequence.map(entry => entry.id || entry.sku),
    name: item.name || `DIY 手串方案 ${index + 1}`,
    desc: item.desc || `${count} 颗 · ${wearStyle}`,
    wristSize,
    wearStyle: item.wearStyle || 'single',
    tone: item.tone || 'clear',
    imageUrl: previewImage,
    preview_image: previewImage,
    previewImage,
    sequence,
    recipeText: item.recipeText || buildRecipeText(sequence),
    miniBeads: createMiniBeads(sequence, Math.max(8, Math.min(sequence.length || 12, 18)), 40, 24, item.placements || []),
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
    selectedKeys: [],
    selectedCount: 0,
    selectedQty: 0,
    subtotal: 0,
    subtotalText: '0.00',
    allSelected: false,
    manageMode: false
  },

  onShow() {
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
          qty: row.quantity
        }));
      wx.setStorageSync(CART_KEY, cart);
    } catch (error) {
      console.warn('load cart fallback:', error.message || error);
    }
    const items = cart.map(normalizeCartItem);
    const validKeys = new Set(items.map(item => item.key));
    let selectedKeys = (this.data.selectedKeys || []).filter(key => validKeys.has(key));
    if (!selectedKeys.length && items.length === 1) selectedKeys = [items[0].key];
    this.applySelection(items, selectedKeys);
  },

  applySelection(items, selectedKeys) {
    const selectedSet = new Set(selectedKeys);
    const nextItems = items.map(item => ({
      ...item,
      selected: selectedSet.has(item.key),
      lineTotal: Number((item.price * item.qty).toFixed(2)),
      lineTotalText: toMoney(item.price * item.qty)
    }));
    const selectedItems = nextItems.filter(item => item.selected);
    const selectedQty = selectedItems.reduce((sum, item) => sum + item.qty, 0);
    const subtotal = selectedItems.reduce((sum, item) => sum + item.price * item.qty, 0);
    this.setData({
      items: nextItems,
      selectedKeys,
      selectedCount: selectedItems.length,
      selectedQty,
      subtotal: Number(subtotal.toFixed(2)),
      subtotalText: toMoney(subtotal),
      allSelected: items.length > 0 && selectedItems.length === items.length
    });
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

  toggleSelect(e) {
    const key = e.currentTarget.dataset.key;
    const selected = new Set(this.data.selectedKeys);
    if (selected.has(key)) selected.delete(key);
    else selected.add(key);
    this.applySelection(this.data.items, Array.from(selected));
  },

  selectAll() {
    const selectedKeys = this.data.allSelected ? [] : this.data.items.map(item => item.key);
    this.applySelection(this.data.items, selectedKeys);
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
    this.applySelection(items, this.data.selectedKeys);
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
    const selectedKeys = this.data.selectedKeys.filter(itemKey => itemKey !== key);
    this.persistItems(items);
    this.applySelection(items, selectedKeys);
    wx.showToast({ title: '已移出购物车', icon: 'none' });
  },

  removeSelected() {
    if (!this.data.selectedKeys.length) {
      wx.showToast({ title: '请先选择方案', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '移出购物车？',
      content: `将移出 ${this.data.selectedCount} 个方案，确定继续吗？`,
      confirmText: '删除',
      confirmColor: '#C83B3D',
      success: res => {
        if (!res.confirm) return;
        this.removeSelectedItems();
      }
    });
  },

  async removeSelectedItems() {
    const selectedSet = new Set(this.data.selectedKeys);
    const selectedItems = this.data.items.filter(item => selectedSet.has(item.key));
    try {
      const user = await auth.requireLogin('登录后才能更新购物车。');
      await Promise.all(selectedItems
        .filter(item => item.cart_item_id)
        .map(item => deleteCartItem(item.cart_item_id, user.user_id)));
    } catch (error) {
      wx.showToast({ title: error.message || '删除购物车失败', icon: 'none' });
      return;
    }
    const items = this.data.items.filter(item => !selectedSet.has(item.key));
    this.persistItems(items);
    this.applySelection(items, []);
  },

  buildDesignPayload(item = {}) {
    return {
      designId: item.designId || item.design_id || '',
      design_id: item.designId || item.design_id || '',
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

  openDesign(e) {
    const key = e.currentTarget.dataset.key;
    const item = this.data.items.find(entry => entry.key === key);
    if (!item) return;
    wx.setStorageSync('currentDesign', this.buildDesignPayload(item));
    wx.setStorageSync('workspaceOpenDesign', 'cart');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  checkoutSelected() {
    const selectedItems = this.data.items.filter(item => item.selected);
    if (!selectedItems.length) {
      wx.showToast({ title: '请先选择方案', icon: 'none' });
      return;
    }
    if (selectedItems.length > 1) {
      wx.showToast({ title: '一次先结算一个方案', icon: 'none' });
      return;
    }
    const item = selectedItems[0];
    wx.setStorageSync('currentDesign', this.buildDesignPayload(item));
    wx.navigateTo({ url: '/pages/checkout/checkout' });
  },

  continueDiy() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  goHome() {
    wx.switchTab({ url: '/pages/home/home' });
  }
});
