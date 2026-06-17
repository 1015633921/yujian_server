const auth = require('../../utils/auth');
const { getMaterials } = require('../../utils/api');

const DEFAULT_MATERIALS = [
  { id: 'clearQuartz8', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 5, size: 8, weight: 1.2, color: '#dfe3e5', shine: '#ffffff' },
  { id: 'clearQuartz10', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 10, size: 10, weight: 1.6, color: '#d6dbde', shine: '#ffffff' },
  { id: 'clearQuartz12', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 15, size: 12, weight: 2.1, color: '#cfd5d8', shine: '#ffffff' },
  { id: 'clearQuartz14', skuId: 'clearQuartz', top: 'bead', category: '白水晶', name: '喜马拉雅白水晶', effect: '净化与放大', element: '金', price: 18, size: 14, weight: 2.8, color: '#c8ced1', shine: '#ffffff' },
  { id: 'amethyst8', skuId: 'amethyst', top: 'bead', category: '紫水晶', name: '乌拉圭紫水晶', effect: '灵感与睡眠', element: '火', price: 12, size: 8, weight: 1.4, color: '#8b6aa5', shine: '#efe8ff' },
  { id: 'amethyst10', skuId: 'amethyst', top: 'bead', category: '紫水晶', name: '乌拉圭紫水晶', effect: '灵感与睡眠', element: '火', price: 18, size: 10, weight: 1.8, color: '#76508f', shine: '#efe8ff' },
  { id: 'citrine8', skuId: 'citrine', top: 'bead', category: '黄水晶', name: '巴西黄水晶', effect: '财富与行动', element: '土', price: 16, size: 8, weight: 1.5, color: '#d6ad50', shine: '#fff0b7' },
  { id: 'citrine10', skuId: 'citrine', top: 'bead', category: '黄水晶', name: '巴西黄水晶', effect: '财富与行动', element: '土', price: 22, size: 10, weight: 1.9, color: '#c79838', shine: '#fff0b7' },
  { id: 'obsidian10', skuId: 'obsidian', top: 'bead', category: '曜石', name: '冰种黑曜石', effect: '边界与守护', element: '金', price: 14, size: 10, weight: 1.8, color: '#262529', shine: '#aeb2b5' },
  { id: 'tigerEye8', skuId: 'tigerEye', top: 'bead', category: '虎眼石', name: '南非虎眼石', effect: '执行与稳定', element: '土', price: 13, size: 8, weight: 1.5, color: '#9b6a2e', shine: '#f1c06b' },
  { id: 'moonstone6', skuId: 'moonstone', top: 'bead', category: '月光石', name: '雪花幽灵', effect: '情绪修复', element: '水', price: 4, size: 6, weight: 0.9, color: '#c7cbca', shine: '#ffffff' },
  { id: 'moonstone8', skuId: 'moonstone', top: 'bead', category: '月光石', name: '雪花幽灵', effect: '情绪修复', element: '水', price: 8, size: 8, weight: 1.2, color: '#bdc2c1', shine: '#ffffff' },
  { id: 'aquamarine8', skuId: 'aquamarine', top: 'bead', category: '海蓝宝', name: '巴西海蓝宝', effect: '沟通与平静', element: '水', price: 25, size: 8, weight: 1.4, color: '#80b8c5', shine: '#e8fbff' },
  { id: 'blueRutilatedQuartz10', skuId: 'blueRutilatedQuartz', top: 'bead', category: '蓝发晶', name: '蓝发晶', effect: '冷静与洞察', element: '水', price: 38, size: 10, weight: 1.9, color: '#4f789b', shine: '#dcecf3' },
  { id: 'garnet8', skuId: 'garnet', top: 'bead', category: '石榴石', name: '石榴石', effect: '活力与自信', element: '火', price: 18, size: 8, weight: 1.5, color: '#8e2635', shine: '#e7a1aa' },
  { id: 'turquoise6', skuId: 'turquoise', top: 'bead', category: '绿松石', name: '绿松石', effect: '生机与恢复', element: '木', price: 16, size: 6, weight: 0.9, color: '#56a6a2', shine: '#d7f1ef' },
  { id: 'greenPhantom8', skuId: 'greenPhantom', top: 'bead', category: '绿幽灵', name: '绿幽灵', effect: '生长与专注', element: '木', price: 24, size: 8, weight: 1.4, color: '#4a825f', shine: '#d7eadc' },
  { id: 'smokyQuartz8', skuId: 'smokyQuartz', top: 'bead', category: '茶晶', name: '茶晶', effect: '稳定与落地', element: '土', price: 14, size: 8, weight: 1.4, color: '#766052', shine: '#d8c8bc' },
  { id: 'hematite8', skuId: 'hematite', top: 'bead', category: '赤铁矿', name: '赤铁矿', effect: '边界与决断', element: '金', price: 12, size: 8, weight: 1.7, color: '#5a5b60', shine: '#d5d6d8' },
  { id: 'roseQuartz8', skuId: 'roseQuartz', top: 'bead', category: '粉水晶', name: '马达加斯加粉晶', effect: '人缘与亲密', element: '木', price: 11, size: 8, weight: 1.3, color: '#e0a3a8', shine: '#fff1f3' },
  { id: 'silverSpacer', skuId: 'silverSpacer', top: 'accessory', category: '隔片', name: '925 银隔片', effect: '结构与光泽', element: '金', price: 18, size: 3, weight: 0.4, color: '#b9bdc2', shine: '#ffffff' },
  { id: 'goldSpacer', skuId: 'goldSpacer', top: 'accessory', category: '隔片', name: '鎏金隔片', effect: '礼物感', element: '土', price: 16, size: 3, weight: 0.4, color: '#c99d4d', shine: '#fff0b7' },
  { id: 'foxPendant', skuId: 'foxPendant', top: 'pendant', category: '吊坠', name: '粉晶狐狸吊坠', effect: '桃花与礼物', element: '木', price: 88, size: 12, weight: 2.2, color: '#d88b91', shine: '#fff1f3' }
];

const TOP_TABS = [
  { key: 'bead', label: '珠珠' },
  { key: 'accessory', label: '配饰' },
  { key: 'incense', label: '合香珠' },
  { key: 'pendant', label: '花托' }
];

const LEGACY_ID_MAP = {
  aquamarine: 'aquamarine8',
  amethyst: 'amethyst8',
  clearQuartz: 'clearQuartz8',
  moonstone: 'moonstone8',
  citrine: 'citrine8',
  tigerEye: 'tigerEye8',
  roseQuartz: 'roseQuartz8',
  obsidian: 'obsidian10',
  lapis: 'aquamarine8'
};

const BACKEND_CRYSTAL_MAP = {
  titanium_quartz: 'citrine10',
  citrine: 'citrine8',
  gold_rutilated_quartz: 'citrine10',
  rhodochrosite: 'roseQuartz8',
  strawberry_quartz: 'roseQuartz8',
  rose_quartz: 'roseQuartz8',
  blue_rutilated_quartz: 'blueRutilatedQuartz10',
  obsidian: 'obsidian10',
  black_rutilated_quartz: 'obsidian10',
  green_phantom: 'greenPhantom8',
  clear_quartz: 'clearQuartz8',
  aquamarine: 'aquamarine8',
  turquoise: 'turquoise6',
  garnet: 'garnet8',
  smoky_quartz: 'smokyQuartz8',
  hematite: 'hematite8'
};

const ELEMENTS = [
  { key: 'wood', name: '木', color: '#4f8f6f' },
  { key: 'fire', name: '火', color: '#c75d45' },
  { key: 'earth', name: '土', color: '#b58b4f' },
  { key: 'metal', name: '金', color: '#9b9fa3' },
  { key: 'water', name: '水', color: '#477b91' }
];

const MATERIAL_ELEMENT_KEY = {
  clearQuartz: 'metal',
  amethyst: 'fire',
  citrine: 'earth',
  obsidian: 'metal',
  tigerEye: 'earth',
  moonstone: 'water',
  aquamarine: 'water',
  blueRutilatedQuartz: 'water',
  roseQuartz: 'wood',
  garnet: 'fire',
  turquoise: 'wood',
  greenPhantom: 'wood',
  smokyQuartz: 'earth',
  hematite: 'metal',
  silverSpacer: 'metal',
  goldSpacer: 'earth',
  foxPendant: 'wood'
};

const ELEMENT_POINT_POSITIONS = [
  { x: 100, y: 12 },
  { x: 180, y: 72 },
  { x: 150, y: 168 },
  { x: 50, y: 168 },
  { x: 20, y: 72 }
];

Page({
  data: {
    materials: DEFAULT_MATERIALS,
    visibleMaterials: [],
    categories: [],
    categoriesByTop: {},
    seriesOptions: ['全部'],
    seriesByCategory: {},
    filterSummary: '全部 · 全部 · 0 款',
    topTabs: TOP_TABS,
    activeTop: 'bead',
    activeCategory: '全部',
    activeSeries: '全部',
    showTip: true,
    wristSize: 16,
    wearStyle: 'single',
    selected: [],
    placements: [],
    selectedItems: [],
    selectedBeadIndex: -1,
    canUndo: false,
    deviceClass: 'device-regular',
    deviceInfo: {},
    energyChart: {
      hasProfile: false,
      matchScore: 0,
      matchText: '--',
      subtitle: '先测算可对比个人档案',
      currentPoints: [],
      targetPoints: [],
      elementRows: [],
      lines: []
    },
    summary: {
      count: 0,
      price: 0,
      priceText: '0.00',
      length: '0.0',
      weight: '0.00',
      maxLength: '17.6',
      warning: '',
      energy: []
    }
  },

  onLoad(query) {
    this.initDeviceLayout();
    this.loadProfileEnergy();
    this.loadMaterials();
    if (query.preset === 'backend-recommended') {
      this.applyBackendRecommendation();
      return;
    }
    if (query.preset === 'recommended') {
      this.applyRecommendedRecipe();
      return;
    }
    this.loadDraft();
  },

  initDeviceLayout() {
    const info = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
    const windowWidth = Number(info.windowWidth) || 375;
    const windowHeight = Number(info.windowHeight) || 667;
    const screenHeight = Number(info.screenHeight) || windowHeight;
    const statusBarHeight = Number(info.statusBarHeight) || 0;
    const safeArea = info.safeArea || {};
    const bottomInset = safeArea.bottom ? Math.max(0, screenHeight - safeArea.bottom) : 0;
    const classes = ['device-regular'];
    if (windowWidth <= 340) classes.push('device-narrow');
    if (windowHeight <= 650) classes.push('device-short');
    if (windowHeight / windowWidth >= 2.05) classes.push('device-tall');
    if (windowWidth >= 414) classes.push('device-wide');
    if (bottomInset > 0) classes.push('device-safe-bottom');
    if (statusBarHeight >= 40) classes.push('device-deep-status');
    this.setData({
      deviceClass: classes.join(' '),
      deviceInfo: {
        windowWidth,
        windowHeight,
        screenHeight,
        statusBarHeight,
        bottomInset
      }
    });
  },

  async loadMaterials() {
    try {
      const data = await getMaterials();
      const materials = data.materials && data.materials.length ? data.materials : DEFAULT_MATERIALS;
      this.setData({
        materials,
        topTabs: data.top_tabs || TOP_TABS,
        categoriesByTop: data.categories_by_top || {},
        seriesByCategory: data.series_by_category || {}
      });
    } catch (error) {
      console.warn('load materials fallback:', error.message || error);
      this.setData({ materials: DEFAULT_MATERIALS, topTabs: TOP_TABS, seriesByCategory: {} });
    } finally {
      this.refreshFilters();
      this.recalculate();
    }
  },

  findMaterialById(id) {
    return this.data.materials.find(material => material.id === id);
  },

  hasMaterial(id) {
    return !!this.findMaterialById(id);
  },

  resolveMaterialId(id) {
    if (this.hasMaterial(id)) return id;
    const legacyId = LEGACY_ID_MAP[id];
    if (legacyId && this.hasMaterial(legacyId)) return legacyId;
    const material = this.data.materials.find(item => item.skuId === id);
    return material ? material.id : id;
  },

  onShow() {
    wx.hideTabBar({ animation: false });
    this.loadProfileEnergy();
    if (wx.getStorageSync('workspacePreset') === 'backend-recommended') {
      wx.removeStorageSync('workspacePreset');
      this.applyBackendRecommendation();
      return;
    }
    if (wx.getStorageSync('workspacePreset') === 'recommended') {
      wx.removeStorageSync('workspacePreset');
      this.applyRecommendedRecipe();
    }
  },

  loadProfileEnergy() {
    const report = wx.getStorageSync('energyReport');
    const targetMap = {};
    const backendKeyMap = { 木: 'wood', 火: 'fire', 土: 'earth', 金: 'metal', 水: 'water' };
    if (report && report.final_energy_profile) {
      Object.keys(report.final_energy_profile).forEach(name => {
        targetMap[backendKeyMap[name]] = Math.max(0, Math.min(100, Number(report.final_energy_profile[name]) * 3));
      });
    } else if (report && report.elements && report.elements.length) {
      report.elements.forEach(item => {
        targetMap[item.key] = Math.max(0, Math.min(100, Number(item.value) || 0));
      });
    }
    this.setData({ userEnergyTarget: targetMap });
  },

  onUnload() {
    wx.showTabBar({ animation: false });
  },

  onHide() {
    wx.showTabBar({ animation: false });
  },

  loadDraft() {
    const draft = wx.getStorageSync('currentDesign');
    if (draft && draft.selected && draft.selected.length) {
      this.setData({
        selected: draft.selected.map(id => LEGACY_ID_MAP[id] || id),
        placements: this.normalizePlacements(draft.selected, draft.placements),
        wristSize: draft.wristSize || 16,
        wearStyle: draft.wearStyle || 'single'
      });
      this.recalculate();
    } else {
      this.recalculate();
    }
  },

  applyRecommendedRecipe() {
    const recipe = wx.getStorageSync('recommendedRecipe') || ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'];
    const wristSize = Number(wx.getStorageSync('recommendedWristSize')) || this.data.wristSize || 16;
    const idMap = {
      aquamarine: 'aquamarine8',
      amethyst: 'amethyst8',
      clearQuartz: 'clearQuartz8',
      moonstone: 'moonstone8',
      citrine: 'citrine8',
      tigerEye: 'tigerEye8',
      roseQuartz: 'roseQuartz8',
      obsidian: 'obsidian10',
      silverSpacer: 'silverSpacer',
      goldSpacer: 'goldSpacer',
      foxPendant: 'foxPendant'
    };
    const materialIds = (recipe.length ? recipe : ['aquamarine', 'amethyst', 'clearQuartz', 'moonstone'])
      .map(id => this.resolveMaterialId(idMap[id] || id))
      .filter(id => this.hasMaterial(id));
    const selected = [];
    const targetLengthMm = wristSize * 10 + 8;
    let currentLengthMm = 0;
    let cursor = 0;
    while (materialIds.length && currentLengthMm < targetLengthMm && selected.length < 40) {
      const materialId = materialIds[cursor % materialIds.length];
      const material = this.findMaterialById(materialId);
      selected.push(materialId);
      currentLengthMm += material ? material.size : 8;
      cursor += 1;
    }
    this.pushHistory();
    this.setData({
      wristSize,
      selected,
      placements: this.normalizePlacements(selected),
      selectedBeadIndex: -1
    });
    this.recalculate();
  },

  applyBackendRecommendation() {
    const payload = wx.getStorageSync('diyWorkbenchPayload');
    if (!payload || !payload.bracelet_plan || !payload.bracelet_plan.layout) {
      wx.showToast({ title: '未找到推荐方案', icon: 'none' });
      this.loadDraft();
      return;
    }
    const selected = payload.bracelet_plan.layout
      .map(item => BACKEND_CRYSTAL_MAP[item.crystal_code])
      .filter(id => this.hasMaterial(id));
    this.pushHistory();
    this.setData({
      wristSize: Number(payload.wrist_size_cm) || 16,
      selected,
      placements: this.normalizePlacements(selected),
      selectedBeadIndex: -1,
      showTip: false
    });
    this.recalculate();
    wx.showToast({ title: '已载入专属推荐', icon: 'success' });
  },

  normalizePlacements(selected, placements) {
    return selected.map((id, index) => {
      return {
        id,
        dx: 0,
        dy: 0
      };
    });
  },

  pushHistory() {
    const history = wx.getStorageSync('workspaceHistory') || [];
    history.push({
      selected: this.data.selected,
      placements: this.data.placements,
      wristSize: this.data.wristSize,
      wearStyle: this.data.wearStyle
    });
    wx.setStorageSync('workspaceHistory', history.slice(-30));
    this.setData({ canUndo: true });
  },

  undo() {
    const history = wx.getStorageSync('workspaceHistory') || [];
    const previous = history.pop();
    if (!previous) {
      wx.showToast({ title: '没有可撤回的操作', icon: 'none' });
      this.setData({ canUndo: false });
      return;
    }
    wx.setStorageSync('workspaceHistory', history);
    this.setData({
      selected: previous.selected || [],
      placements: previous.placements || [],
      wristSize: previous.wristSize || 16,
      wearStyle: previous.wearStyle || 'single',
      selectedBeadIndex: -1,
      canUndo: history.length > 0
    });
    this.recalculate();
  },

  refreshFilters() {
    const pool = this.data.materials.filter(item => item.top === this.data.activeTop);
    const backendCategories = this.data.categoriesByTop[this.data.activeTop] || [];
    const categoryNames = backendCategories.length ? backendCategories : ['全部', ...Array.from(new Set(pool.map(item => item.category)))];
    const activeCategory = categoryNames.includes(this.data.activeCategory) ? this.data.activeCategory : '全部';
    const categoryPool = pool.filter(item => activeCategory === '全部' || item.category === activeCategory);
    const seriesKey = `${this.data.activeTop}::${activeCategory}`;
    const backendSeries = this.data.seriesByCategory[seriesKey] || [];
    const localSeries = ['全部', ...Array.from(new Set(categoryPool.map(item => item.series || item.name).filter(Boolean)))];
    const seriesOptions = activeCategory === '全部' ? ['全部'] : (backendSeries.length ? backendSeries : localSeries);
    const activeSeries = seriesOptions.includes(this.data.activeSeries) ? this.data.activeSeries : '全部';
    const visibleMaterials = categoryPool.filter(item => {
      const series = item.series || item.name || '';
      return activeSeries === '全部' || series === activeSeries;
    });
    const filterSummary = `${activeCategory} · ${activeSeries} · ${visibleMaterials.length} 款`;
    this.setData({ categories: categoryNames, activeCategory, seriesOptions, activeSeries, visibleMaterials, filterSummary });
  },

  selectTop(e) {
    this.setData({ activeTop: e.currentTarget.dataset.top, activeCategory: '全部', activeSeries: '全部' });
    this.refreshFilters();
  },

  selectCategory(e) {
    this.setData({ activeCategory: e.currentTarget.dataset.category, activeSeries: '全部' });
    this.refreshFilters();
  },

  selectSeries(e) {
    this.setData({ activeSeries: e.currentTarget.dataset.series });
    this.refreshFilters();
  },

  onMaterialImageError(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    const materials = this.data.materials.map(item => (
      item.id === id ? { ...item, image_url: '' } : item
    ));
    this.setData({ materials });
    this.refreshFilters();
    this.recalculate();
  },

  closeTip() {
    this.setData({ showTip: false });
  },

  openWristSetting() {
    wx.showActionSheet({
      itemList: ['14cm', '15cm', '16cm', '17cm', '18cm', '19cm'],
      success: res => {
        const wristSize = 14 + res.tapIndex;
        this.pushHistory();
        this.setData({ wristSize });
        this.recalculate();
      }
    });
  },

  openToolbox() {
    wx.showActionSheet({
      itemList: ['撤回上一步', '保存草稿', '清空设计'],
      success: res => {
        if (res.tapIndex === 0) this.undo();
        if (res.tapIndex === 1) this.saveDraft();
        if (res.tapIndex === 2) this.clearDesign();
      }
    });
  },

  toggleWearStyle() {
    this.pushHistory();
    this.setData({ wearStyle: this.data.wearStyle === 'single' ? 'double' : 'single' });
    this.recalculate();
  },

  addMaterial(e) {
    const id = e.currentTarget.dataset.id;
    this.pushHistory();
    if (wx.vibrateShort) wx.vibrateShort({ type: 'light' });
    this.setData({
      selected: [...this.data.selected, id],
      placements: [...this.data.placements, { id, dx: 0, dy: 0 }],
      selectedBeadIndex: this.data.selected.length
    });
    this.recalculate();
  },

  removeItem(e) {
    const index = Number(e.currentTarget.dataset.index);
    this.pushHistory();
    const selected = [...this.data.selected];
    const placements = [...this.data.placements];
    selected.splice(index, 1);
    placements.splice(index, 1);
    this.setData({ selected, placements, selectedBeadIndex: -1 });
    this.recalculate();
  },

  clearDesign() {
    if (this.data.selected.length) this.pushHistory();
    this.setData({ selected: [], placements: [], selectedBeadIndex: -1 });
    this.recalculate();
  },

  confirmClearDesign() {
    if (!this.data.selected.length) {
      wx.showToast({ title: '盘面已经是空的', icon: 'none' });
      return;
    }
    wx.showModal({
      title: '清空盘面',
      content: '确定要清空当前手串设计吗？',
      confirmText: '清空',
      confirmColor: '#7a4e3a',
      success: res => {
        if (res.confirm) {
          this.clearDesign();
          if (wx.vibrateShort) wx.vibrateShort({ type: 'medium' });
        }
      }
    });
  },

  selectBead(e) {
    const index = Number(e.currentTarget.dataset.index);
    this.setData({ selectedBeadIndex: index });
    this.recalculate();
  },

  nudgeSelected(e) {
    this.moveSelectedOrder(e);
  },

  moveSelectedOrder(e) {
    const index = this.data.selectedBeadIndex;
    const direction = Number(e.currentTarget.dataset.direction);
    const nextIndex = index + direction;
    if (index < 0) {
      wx.showToast({ title: '先点选一颗珠子', icon: 'none' });
      return;
    }
    if (nextIndex < 0 || nextIndex >= this.data.selected.length) {
      wx.showToast({ title: '已经到边界了', icon: 'none' });
      return;
    }
    const selected = [...this.data.selected];
    const placements = this.normalizePlacements(selected, this.data.placements);
    const selectedItem = selected[index];
    const placementItem = placements[index];
    selected[index] = selected[nextIndex];
    selected[nextIndex] = selectedItem;
    placements[index] = placements[nextIndex];
    placements[nextIndex] = placementItem;
    this.pushHistory();
    this.setData({ selected, placements, selectedBeadIndex: nextIndex });
    this.recalculate();
  },

  recalculate() {
    const items = this.data.selected.map(id => this.findMaterialById(id)).filter(Boolean);
    const price = items.reduce((sum, item) => sum + item.price, 0);
    const length = items.reduce((sum, item) => sum + item.size, 0) / 10;
    const weight = items.reduce((sum, item) => sum + item.weight, 0);
    const maxLength = this.data.wearStyle === 'double' ? this.data.wristSize * 2.2 : this.data.wristSize * 1.1;
    const warning = items.length === 0 ? '' : length > maxLength ? '偏长' : length < maxLength - 1.6 ? '偏短' : '合适';
    const placements = this.normalizePlacements(this.data.selected, this.data.placements);
    const selectedItems = this.layoutSelectedItems(items, placements);
    const counts = {};
    items.forEach(item => {
      const key = MATERIAL_ELEMENT_KEY[item.skuId] || 'metal';
      counts[key] = (counts[key] || 0) + 1;
    });
    const energy = ELEMENTS.map(element => ({
      ...element,
      value: items.length ? Math.round(((counts[element.key] || 0) / items.length) * 100) : 0
    }));
    const energyChart = this.buildEnergyChart(energy);
    const summary = {
      count: items.length,
      price,
      priceText: price.toFixed(2),
      length: length.toFixed(1),
      weight: weight.toFixed(2),
      maxLength: maxLength.toFixed(1),
      warning,
      energy
    };
    this.setData({ summary, selectedItems, placements, energyChart });
    wx.setStorageSync('currentDesign', {
      selected: this.data.selected,
      placements,
      wristSize: this.data.wristSize,
      wearStyle: this.data.wearStyle,
      summary
    });
  },

  buildEnergyChart(currentEnergy) {
    const targetMap = this.data.userEnergyTarget || {};
    const hasProfile = Object.keys(targetMap).length > 0;
    const targetEnergy = ELEMENTS.map(element => ({
      ...element,
      value: hasProfile ? (targetMap[element.key] || 0) : 50
    }));
    const currentPoints = this.buildStarPoints(currentEnergy, 7);
    const targetPoints = this.buildStarPoints(targetEnergy, 4);
    const elementRows = ELEMENTS.map((element, index) => {
      const current = currentEnergy[index].value;
      const target = targetEnergy[index].value;
      return {
        ...element,
        current,
        target,
        delta: current - target,
        currentWidth: `${current}%`,
        targetWidth: `${target}%`
      };
    });
    const matchScore = hasProfile
      ? Math.max(0, Math.round(100 - elementRows.reduce((sum, item) => sum + Math.abs(item.delta), 0) / 5))
      : 0;
    return {
      hasProfile,
      matchScore,
      matchText: hasProfile ? `${matchScore}%` : '--',
      subtitle: hasProfile ? '手串 / 档案目标' : '先测算可对比个人档案',
      currentPoints,
      targetPoints,
      elementRows,
      lines: this.buildStarLines(currentPoints)
    };
  },

  buildStarPoints(energy, dotSize) {
    const center = { x: 100, y: 100 };
    return energy.map((item, index) => {
      const base = ELEMENT_POINT_POSITIONS[index];
      const value = Math.max(0, Math.min(100, item.value));
      const x = center.x + (base.x - center.x) * value / 100;
      const y = center.y + (base.y - center.y) * value / 100;
      return {
        key: item.key,
        name: item.name,
        value,
        color: item.color,
        style: `left:${(x - dotSize / 2).toFixed(1)}rpx;top:${(y - dotSize / 2).toFixed(1)}rpx;width:${dotSize}rpx;height:${dotSize}rpx;background:${item.color};`
      };
    });
  },

  buildStarLines(points) {
    return points.map((point, index) => {
      const next = points[(index + 1) % points.length];
      const x1 = Number(point.style.match(/left:([0-9.-]+)rpx/)[1]) + 3.5;
      const y1 = Number(point.style.match(/top:([0-9.-]+)rpx/)[1]) + 3.5;
      const x2 = Number(next.style.match(/left:([0-9.-]+)rpx/)[1]) + 3.5;
      const y2 = Number(next.style.match(/top:([0-9.-]+)rpx/)[1]) + 3.5;
      const length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
      const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
      return {
        key: `${point.key}-${next.key}`,
        style: `left:${x1.toFixed(1)}rpx;top:${y1.toFixed(1)}rpx;width:${length.toFixed(1)}rpx;transform:rotate(${angle.toFixed(1)}deg);`
      };
    });
  },

  layoutSelectedItems(items, placements) {
    const count = Math.max(items.length, 1);
    const layout = this.getStageLayout();
    const radius = layout.radius;
    const center = layout.center;
    return items.map((item, index) => {
      const angle = -90 + (360 / count) * index;
      const rad = angle * Math.PI / 180;
      const beadSize = Math.max(42, Math.min(78, item.size * 5.4));
      const placement = placements[index] || { dx: 0, dy: 0 };
      const left = center + Math.cos(rad) * radius - beadSize / 2 + placement.dx;
      const top = center + Math.sin(rad) * radius - beadSize / 2 + placement.dy;
      return {
        ...item,
        index,
        selected: index === this.data.selectedBeadIndex,
        beadSize,
        shortName: item.name.slice(0, 1),
        style: `left:${left.toFixed(1)}rpx;top:${top.toFixed(1)}rpx;width:${beadSize}rpx;height:${beadSize}rpx;background:radial-gradient(circle at 32% 28%, ${item.shine} 0 10%, ${item.color} 12% 58%, rgba(0,0,0,.22) 100%);`
      };
    });
  },

  getStageLayout() {
    const deviceClass = this.data.deviceClass || '';
    if (deviceClass.includes('device-short')) {
      return { center: 250, radius: 194 };
    }
    if (deviceClass.includes('device-wide')) {
      return { center: 293, radius: 228 };
    }
    if (deviceClass.includes('device-narrow')) {
      return { center: 258, radius: 200 };
    }
    return { center: 280, radius: 218 };
  },

  async saveDraft() {
    let user;
    try {
      user = await auth.requireLogin('登录后才能保存 DIY 草稿。');
    } catch (error) {
      return false;
    }
    wx.setStorageSync('currentDesign', {
      userId: user.user_id,
      selected: this.data.selected,
      placements: this.data.placements,
      wristSize: this.data.wristSize,
      wearStyle: this.data.wearStyle,
      summary: this.data.summary
    });
    wx.showToast({ title: '已保存', icon: 'success' });
    return true;
  },

  async goToCheckout() {
    if (!this.data.selected.length) {
      wx.showToast({ title: '先选择至少一颗材料', icon: 'none' });
      return;
    }
    const saved = await this.saveDraft();
    if (!saved) return;
    wx.navigateTo({ url: '/pages/checkout/checkout' });
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/home/home' });
  }
});
