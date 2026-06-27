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

function beadIdsFromDesign(design = {}) {
  if (Array.isArray(design.selected) && design.selected.length) return design.selected;
  if (Array.isArray(design.sequence) && design.sequence.length) return design.sequence.map(item => item.id || item.sku).filter(Boolean);
  return [];
}

function createPreviewBeads(ids = []) {
  const safeIds = ids.length ? ids.slice(0, 16) : ['moonstone', 'clearQuartz', 'amethyst', 'clearQuartz'];
  const count = Math.max(safeIds.length, 8);
  return Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index;
    const id = safeIds[index % safeIds.length];
    return {
      src: ASSETS[id] || ASSETS.clearQuartz,
      style: `width:28rpx;height:28rpx;transform:rotate(${angle}deg) translateY(-46rpx) rotate(${-angle}deg);`
    };
  });
}

function normalizeSavedPlan(item = {}, index = 0, source = 'draft') {
  const selected = beadIdsFromDesign(item);
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
    recipeText: selected.slice(0, 4).map(id => MATERIAL_NAMES[id] || id).join(' · ') || '待继续编辑',
    previewBeads: createPreviewBeads(selected),
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
  const design = order.design || {};
  const selected = beadIdsFromDesign({ ...design, sequence: order.sequence || design.sequence });
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
    recipeText: selected.slice(0, 4).map(id => MATERIAL_NAMES[id] || id).join(' · ') || '查看订单材料',
    previewBeads: createPreviewBeads(selected),
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
