const { assetUrl } = require('../../utils/assets');

const MATERIAL_NAMES = {
  aquamarine: '海蓝宝',
  amethyst: '紫水晶',
  clearQuartz: '白水晶',
  moonstone: '月光石',
  citrine: '黄水晶',
  tigerEye: '虎眼石',
  roseQuartz: '粉晶',
  obsidian: '黑曜石',
  silverSpacer: '银色隔珠',
  goldSpacer: '金色隔珠',
  foxPendant: '狐狸吊坠'
};

const ASSETS = {
  aquamarine: assetUrl('home/aquamarine.webp'),
  amethyst: assetUrl('home/amethyst.webp'),
  clearQuartz: assetUrl('home/clear-quartz.webp'),
  moonstone: assetUrl('home/moonstone.webp'),
  citrine: assetUrl('home/citrine.webp'),
  tigerEye: assetUrl('home/citrine.webp'),
  roseQuartz: assetUrl('home/moonstone.webp'),
  obsidian: assetUrl('home/amethyst.webp')
};
const PLAN_TRAY_IMAGES = {
  white: assetUrl('workspace/tray-yustream-white-transparent-user-20260701.webp'),
  warm: assetUrl('workspace/tray-yustream-transparent-user-20260701-v6.webp'),
  black: assetUrl('workspace/tray-yustream-black-transparent-user-20260701.webp')
};

const TABS = [
  { key: 'all', label: '全部', count: 0 },
  { key: 'saved', label: '已保存', count: 0 },
  { key: 'ordered', label: '已下单', count: 0 },
  { key: 'completed', label: '已完成', count: 0 }
];

function formatDate(value) {
  if (!value) return '刚刚保存';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function moneyText(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
}

function isInternalMaterialId(value) {
  const text = String(value || '').trim();
  return /^(mat|real)[_-]/i.test(text) || /^\d{10,}$/.test(text);
}

function cleanMaterialLabel(value) {
  const text = String(value || '').trim();
  if (!text || text === '-' || text === 'NaN') return '';
  if (isInternalMaterialId(text)) return '';
  return text;
}

function materialLabelFromEntry(entry = {}) {
  if (!entry || typeof entry !== 'object') {
    return cleanMaterialLabel(MATERIAL_NAMES[entry] || entry);
  }
  const id = entry.id || entry.sku || entry.material_id || entry.materialId || entry.sku_id || entry.skuId || '';
  const candidates = [
    entry.name,
    entry.material_name,
    entry.materialName,
    entry.series,
    entry.category,
    MATERIAL_NAMES[id],
    id
  ];
  for (let index = 0; index < candidates.length; index += 1) {
    const label = cleanMaterialLabel(candidates[index]);
    if (label) return label;
  }
  return '';
}

function buildRecipeText(design = {}, selected = []) {
  const source = Array.isArray(design.sequence) && design.sequence.length
    ? design.sequence
    : selected;
  const counts = {};
  source.forEach(item => {
    const label = materialLabelFromEntry(item);
    if (!label) return;
    counts[label] = (counts[label] || 0) + 1;
  });
  const labels = Object.keys(counts).map(label => (
    counts[label] > 1 ? `${label} ×${counts[label]}` : label
  ));
  if (labels.length) return labels.slice(0, 4).join(' · ');
  return selected.length ? `${selected.length} 颗定制珠材` : '待继续编辑';
}

function beadIdsFromDesign(design = {}) {
  if (Array.isArray(design.selected) && design.selected.length) return design.selected;
  if (Array.isArray(design.sequence) && design.sequence.length) return design.sequence.map(item => item.id || item.sku).filter(Boolean);
  return [];
}

function previewSequenceFromDesign(design = {}, selected = []) {
  if (Array.isArray(design.sequence) && design.sequence.length) return design.sequence;
  return selected.map(id => ({
    id,
    name: MATERIAL_NAMES[id] || id,
    image_url: ASSETS[id] || '',
    size: 8
  }));
}

function previewTrayFromDesign(design = {}) {
  const trayTheme = design.trayTheme || design.tray_theme || 'white';
  return {
    trayTheme,
    trayImage: design.trayImageUrl
      || design.tray_image_url
      || PLAN_TRAY_IMAGES[trayTheme]
      || PLAN_TRAY_IMAGES.white
  };
}

function normalizeSavedPlan(item = {}, index = 0, source = 'draft') {
  const selected = beadIdsFromDesign(item);
  const tray = previewTrayFromDesign(item);
  const summary = item.summary || {};
  const createdAt = item.updatedAt || item.createdAt || item.savedAt || Date.now();
  const wristSize = item.wristSize || summary.wristSize || summary.targetWristText || '15.0cm';
  const name = item.name || item.title || (source === 'current' ? '当前编辑方案' : `自由搭配方案 ${index + 1}`);

  return {
    key: `${source}-${item.id || item.designId || createdAt || index}`,
    id: item.id || item.designId || '',
    type: 'saved',
    statusKey: 'saved',
    statusText: '已保存',
    statusClass: 'saved',
    name,
    wristSize,
    dateText: `保存于 ${formatDate(createdAt)}`,
    priceText: moneyText(summary.priceText || summary.price || item.price),
    beadCount: selected.length,
    recipeText: buildRecipeText(item, selected),
    previewDesign: item,
    previewSequence: previewSequenceFromDesign(item, selected),
    previewPlacements: item.placements || [],
    trayTheme: tray.trayTheme,
    trayImage: tray.trayImage,
    trayImageFailed: false,
    snapshot: {
      ...item,
      selected,
      summary: {
        ...summary,
        priceText: summary.priceText || summary.price || item.price || 0,
        wristSize
      }
    },
    source
  };
}

function normalizeOrderPlan(order = {}, index = 0) {
  const orderSequence = Array.isArray(order.sequence) && order.sequence.length
    ? order.sequence
    : ((order.design && order.design.sequence) || []);
  const design = {
    ...(order.design || {}),
    sequence: orderSequence,
    trayTheme: (order.design && (order.design.trayTheme || order.design.tray_theme))
      || order.trayTheme
      || order.tray_theme,
    trayImageUrl: (order.design && (order.design.trayImageUrl || order.design.tray_image_url))
      || order.trayImageUrl
      || order.tray_image_url
  };
  const selected = beadIdsFromDesign(design);
  const tray = previewTrayFromDesign(design);
  const isCompleted = order.statusKey === 'done' || order.rawStatus === 'completed' || order.status === '已完成';
  const statusText = isCompleted ? '已完成' : '已下单';
  const wristSize = (design.summary && (design.summary.wristSize || design.summary.targetWristText)) || design.wristSize || '15.0cm';

  return {
    key: `order-${order.id || order.order_id || index}`,
    id: order.id || order.order_id || '',
    type: 'order',
    statusKey: isCompleted ? 'completed' : 'ordered',
    statusText,
    statusClass: isCompleted ? 'completed' : 'ordered',
    name: (design.summary && design.summary.name) || order.title || (isCompleted ? '已完成定制方案' : '已下单定制方案'),
    wristSize,
    dateText: `${isCompleted ? '完成于' : '下单于'} ${formatDate(order.createdAt || order.created_at)}`,
    priceText: moneyText(order.totalAmount || order.total_amount || (design.summary && design.summary.price)),
    beadCount: selected.length || (order.bom || []).reduce((sum, item) => sum + Number(item.qty || 0), 0),
    recipeText: buildRecipeText(design, selected) || '查看订单材料',
    previewDesign: design,
    previewSequence: previewSequenceFromDesign(design, selected),
    previewPlacements: design.placements || order.placements || [],
    trayTheme: tray.trayTheme,
    trayImage: tray.trayImage,
    trayImageFailed: false,
    order
  };
}

Page({
  data: {
    tabs: TABS,
    activeTab: 'all',
    plans: [],
    visiblePlans: [],
    counts: { all: 0, saved: 0, ordered: 0, completed: 0 }
  },

  onShow() {
    this.loadPlans();
  },

  loadPlans() {
    const plans = [];
    const currentDesign = wx.getStorageSync('currentDesign') || null;
    const savedDesigns = wx.getStorageSync('diyDesignCart') || [];
    const orders = wx.getStorageSync('orders') || [];

    if (currentDesign && beadIdsFromDesign(currentDesign).length) {
      plans.push(normalizeSavedPlan(currentDesign, 0, 'current'));
    }

    savedDesigns
      .slice()
      .reverse()
      .forEach((item, index) => {
        if (beadIdsFromDesign(item).length) plans.push(normalizeSavedPlan(item, index, 'saved'));
      });

    orders.forEach((order, index) => {
      plans.push(normalizeOrderPlan(order, index));
    });

    const counts = {
      all: plans.length,
      saved: plans.filter(item => item.statusKey === 'saved').length,
      ordered: plans.filter(item => item.statusKey === 'ordered').length,
      completed: plans.filter(item => item.statusKey === 'completed').length
    };
    const activeTab = this.data.activeTab;
    this.setData({
      plans,
      counts,
      tabs: TABS.map(item => ({ ...item, count: counts[item.key] || 0 })),
      visiblePlans: this.filterPlans(plans, activeTab)
    });
  },

  filterPlans(plans, tab) {
    if (tab === 'all') return plans;
    return plans.filter(item => item.statusKey === tab);
  },

  switchTab(e) {
    const key = e.currentTarget.dataset.key || 'all';
    this.setData({
      activeTab: key,
      visiblePlans: this.filterPlans(this.data.plans, key)
    });
  },

  onTrayImageError(e) {
    const key = e.currentTarget.dataset.key;
    const plans = (this.data.plans || []).map(plan => (
      plan.key === key ? { ...plan, trayImageFailed: true } : plan
    ));
    this.setData({
      plans,
      visiblePlans: this.filterPlans(plans, this.data.activeTab)
    });
  },

  openPlan(e) {
    const key = e.currentTarget.dataset.key;
    const plan = this.data.plans.find(item => item.key === key);
    if (!plan) return;
    if (plan.type === 'order') {
      wx.navigateTo({ url: `/pages/order-detail/order-detail?id=${encodeURIComponent(plan.id)}` });
      return;
    }
    this.continueEditPlan(plan);
  },

  continueEdit(e) {
    const key = e.currentTarget.dataset.key;
    const plan = this.data.plans.find(item => item.key === key);
    if (plan) this.continueEditPlan(plan);
  },

  continueEditPlan(plan) {
    wx.setStorageSync('currentDesign', plan.snapshot);
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  checkoutPlan(e) {
    const key = e.currentTarget.dataset.key;
    const plan = this.data.plans.find(item => item.key === key);
    if (!plan || !plan.snapshot) return;
    wx.setStorageSync('currentDesign', plan.snapshot);
    wx.navigateTo({
      url: '/pages/checkout/checkout',
      fail: () => wx.showToast({ title: '进入结算失败，请重试', icon: 'none' })
    });
  },

  deletePlan(e) {
    const key = e.currentTarget.dataset.key;
    const plan = this.data.plans.find(item => item.key === key);
    if (!plan || plan.type !== 'saved') return;
    wx.showModal({
      title: '删除保存方案？',
      content: '删除后不会影响已下单订单，只会移除本地保存的草稿。',
      confirmText: '删除',
      confirmColor: '#C83B3D',
      success: res => {
        if (!res.confirm) return;
        if (plan.source === 'current') {
          wx.removeStorageSync('currentDesign');
        } else {
          const savedDesigns = wx.getStorageSync('diyDesignCart') || [];
          wx.setStorageSync('diyDesignCart', savedDesigns.filter(item => `saved-${item.id || item.designId || item.createdAt || ''}` !== key));
        }
        this.loadPlans();
      }
    });
  },

  createPlan() {
    wx.navigateTo({ url: '/pages/custom-mode/custom-mode' });
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/profile/profile' });
  }
});
