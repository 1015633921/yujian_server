const auth = require('../../utils/auth');
const { getMaterials, saveCommunityFavorite } = require('../../utils/api');

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
        results: (data.materials || []).map(item => this.normalizeMaterial(item)),
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

  normalizeMaterial(item = {}) {
    const sku = item.sku || {};
    const energy = item.energy || {};
    const visual = item.visual || {};
    const effects = energy.effects || [];
    return {
      ...item,
      id: sku.id || item.id,
      material_code: sku.material_code || item.material_code,
      sku_id: sku.sku_id || item.skuId || item.sku_id,
      name: sku.name || item.name,
      price: Number(sku.price_per_bead || item.price || 0),
      size: Number(sku.size_mm || item.size || 0),
      element: energy.primary_element || item.primary_element || item.element,
      effect: effects.join(' / ') || item.effect,
      effects,
      image_url: visual.thumbnail_url || item.thumbnail_url || item.image_url
    };
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({
      results: this.data.results.map(item => (
        item.id === id ? { ...item, image_url: '' } : item
      ))
    });
  },

  async addToInspiration(e) {
    const item = this.findMaterial(e.currentTarget.dataset.id);
    if (!item) return;
    let user;
    try {
      user = await auth.requireLogin('登录后才能收藏灵感。');
    } catch (error) {
      return;
    }
    const favoriteItem = {
      id: `material:${item.id}`,
      source_id: item.id,
      favorite_type: 'material_inspiration',
      name: item.name,
      title: item.name,
      desc: item.effect,
      price: item.price,
      tone: this.toneForMaterial(item),
      recipe: [item.sku_id],
      materialCode: item.material_code,
      materialId: item.id,
      image_url: item.image_url,
      addedAt: Date.now()
    };
    try {
      await saveCommunityFavorite({
        user_id: user.user_id,
        post_id: favoriteItem.id,
        item: favoriteItem
      });
      wx.showToast({ title: '已收藏', icon: 'none' });
    } catch (error) {
      wx.showToast({ title: error.message || '收藏失败，请重试', icon: 'none' });
    }
    return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const nextItem = {
      name: item.name,
      desc: item.effect,
      price: item.price,
      tone: this.toneForMaterial(item),
      recipe: [item.sku_id],
      materialCode: item.material_code,
      materialId: item.id,
      image_url: item.image_url,
      addedAt: Date.now()
    };
    const exists = cart.some(entry => entry.materialId === item.id || entry.name === item.name);
    const nextCart = exists ? cart : [nextItem, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    wx.showToast({ title: exists ? '已在收藏中' : '已收藏灵感', icon: 'none' });
  },

  startDiy(e) {
    const item = this.findMaterial(e.currentTarget.dataset.id);
    if (!item) return;
    wx.setStorageSync('recommendedRecipe', [item.sku_id]);
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
