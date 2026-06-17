const { getMaterials } = require('../../utils/api');

Page({
  data: {
    keyword: '',
    hotKeywords: ['海蓝宝', '睡眠', '招财', '粉晶', '配饰', '花托'],
    results: [],
    loading: false,
    hasSearched: false
  },

  onLoad(options) {
    const keyword = options.keyword || '';
    this.setData({ keyword });
    this.search(keyword);
  },

  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  submitSearch() {
    this.search(this.data.keyword);
  },

  tapKeyword(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ keyword });
    this.search(keyword);
  },

  clearKeyword() {
    this.setData({ keyword: '', hasSearched: false });
    this.search('');
  },

  async search(keyword) {
    this.setData({ loading: true });
    try {
      const data = await getMaterials({ keyword });
      this.setData({
        results: data.materials || [],
        hasSearched: !!keyword
      });
    } catch (error) {
      console.error('search materials failed:', error);
      wx.showToast({ title: '搜索失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  findMaterial(id) {
    return this.data.results.find(item => item.id === id);
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({
      results: this.data.results.map(item => (
        item.id === id ? { ...item, image_url: '' } : item
      ))
    });
  },

  addToInspiration(e) {
    const item = this.findMaterial(e.currentTarget.dataset.id);
    if (!item) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const nextItem = {
      name: item.name,
      desc: item.effect,
      price: item.price,
      tone: this.toneForMaterial(item),
      recipe: [item.skuId],
      materialId: item.id,
      image_url: item.image_url,
      addedAt: Date.now()
    };
    const exists = cart.some(entry => entry.materialId === item.id || entry.name === item.name);
    const nextCart = exists ? cart : [nextItem, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    wx.showToast({ title: exists ? '灵感单里已有' : '已加入灵感单', icon: 'none' });
  },

  startDiy(e) {
    const item = this.findMaterial(e.currentTarget.dataset.id);
    if (!item) return;
    wx.setStorageSync('recommendedRecipe', [item.skuId]);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  toneForMaterial(item) {
    if (item.element === '火') return 'violet';
    if (item.element === '土') return 'gold';
    if (item.element === '木') return 'pink';
    return 'blue';
  }
});
