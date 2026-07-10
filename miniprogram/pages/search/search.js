const auth = require('../../utils/auth');
const { getCommunityPosts: getLocalCommunityPosts } = require('../../utils/communityData');
const { getRecommendations: getLocalRecommendations } = require('../../utils/recommendationData');
const { getMaterials, saveCommunityFavorite } = require('../../utils/api');

function textOf(value) {
  if (Array.isArray(value)) return value.map(textOf).join(' ');
  if (value && typeof value === 'object') return Object.values(value).map(textOf).join(' ');
  return `${value || ''}`.toLowerCase();
}

function normalizeKeyword(value) {
  return `${value || ''}`.trim().toLowerCase();
}

function materialRowsOf(data) {
  if (Array.isArray(data)) return data;
  return data && (data.materials || data.items || data.data || data.rows) || [];
}

Page({
  data: {
    keyword: '',
    hotKeywords: ['海蓝宝', '放松', '目标感', '粉晶', '配饰', '花托'],
    results: [],
    materialResults: [],
    recommendedInspirations: [],
    inspirationResults: [],
    resultCount: 0,
    loading: false,
    hasSearched: false
  },

  onLoad(options) {
    const keyword = options.keyword || '';
    this.allInspirations = this.buildInspirations();
    this.setData({
      keyword,
      recommendedInspirations: this.allInspirations.slice(0, 6)
    });
    this.search(keyword);
  },

  onUnload() {
    clearTimeout(this.searchTimer);
  },

  onKeywordInput(e) {
    const keyword = e.detail.value;
    this.setData({ keyword });
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.search(keyword);
    }, 260);
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
    clearTimeout(this.searchTimer);
    this.setData({
      keyword: '',
      results: [],
      materialResults: [],
      inspirationResults: [],
      resultCount: 0,
      hasSearched: false
    });
  },

  buildInspirations() {
    const plans = getLocalRecommendations().map(item => this.decorateInspiration(item, 'plan'));
    const posts = getLocalCommunityPosts().map(item => this.decorateInspiration(item, 'community'));
    return [...plans, ...posts];
  },

  decorateInspiration(item = {}, type) {
    const title = item.title || item.name || '灵感方案';
    const desc = item.desc || item.subtitle || item.story || item.scene || '';
    const meta = (item.tags && item.tags.length ? item.tags.join(' / ') : item.scene) || '可带入 DIY 微调';
    const tone = this.normalizeTone(item.tone || item.theme);
    return {
      id: item.id,
      type,
      title,
      desc,
      meta,
      tone,
      searchText: textOf([title, desc, meta, item.materials, item.tags, item.scenes, item.recipe])
    };
  },

  async search(keyword) {
    const normalized = normalizeKeyword(keyword);
    if (!normalized) {
      this.setData({
        results: [],
        materialResults: [],
        inspirationResults: [],
        resultCount: 0,
        hasSearched: false,
        loading: false
      });
      return;
    }

    this.setData({ loading: true, hasSearched: true });
    const inspirationResults = (this.allInspirations || this.buildInspirations())
      .filter(item => item.searchText.includes(normalized))
      .slice(0, 12);

    try {
      const data = await getMaterials({
        keyword: normalized,
        compact: true,
        slim: true,
        pageSize: 24,
        limit: 24,
        silent: true,
        timeout: 8000
      });
      const materialResults = materialRowsOf(data)
        .map(item => this.normalizeMaterial(item))
        .filter(item => item.id && item.name);
      this.setData({
        results: materialResults,
        materialResults,
        inspirationResults,
        resultCount: materialResults.length + inspirationResults.length
      });
    } catch (error) {
      console.error('search materials failed:', error);
      this.setData({
        results: [],
        materialResults: [],
        inspirationResults,
        resultCount: inspirationResults.length
      });
      wx.showToast({ title: '搜索失败，请稍后重试', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  findMaterial(id) {
    return this.data.results.find(item => item.id === id || item.sku_id === id);
  },

  normalizeMaterial(item = {}) {
    const sku = item.sku || item;
    const energy = item.energy || {};
    const visual = item.visual || {};
    const effects = energy.effects || item.effects || [];
    const price = Number(
      sku.price_per_bead ?? item.price_per_bead ?? sku.price ?? item.price ?? 0
    );
    const size = Number(
      sku.size_mm ?? item.size_mm ?? sku.size ?? item.size ?? 0
    );
    const name = sku.name || item.name || sku.material_name || item.material_name || '';
    const element = energy.primary_element || item.primary_element || sku.primary_element || item.element;
    const categoryName = item.category_name || sku.category_name || item.category || '';
    return {
      ...item,
      id: `${sku.id || item.id || sku.sku_id || item.sku_id || item.material_code || name}`,
      material_code: sku.material_code || item.material_code,
      sku_id: sku.sku_id || item.sku_id || sku.id || item.id,
      name,
      price,
      priceText: price.toFixed(2),
      size,
      sizeText: size ? `${size}mm` : '规格可选',
      element,
      categoryName,
      effect: effects.join(' / ') || item.effect || energy.summary || categoryName || '可用于 DIY 搭配',
      effects,
      image_url: visual.thumbnail_url || visual.image_url || sku.thumbnail_url || sku.image_url || item.thumbnail_url || item.image_url || '',
      tone: this.toneForMaterial({ element })
    };
  },

  onImageError(e) {
    const id = e.currentTarget.dataset.id;
    const materialResults = this.data.materialResults.map(item => (
      item.id === id ? { ...item, image_url: '' } : item
    ));
    this.setData({
      materialResults,
      results: materialResults
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
      tone: item.tone,
      recipe: [item.sku_id || item.id],
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
  },

  startDiy(e) {
    const item = this.findMaterial(e.currentTarget.dataset.id);
    if (!item) return;
    wx.setStorageSync('recommendedRecipe', [item.sku_id || item.id]);
    wx.setStorageSync('workspacePreset', 'recommended');
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  openInspiration(e) {
    const id = e.currentTarget.dataset.id;
    const type = e.currentTarget.dataset.type;
    if (!id) return;
    if (type === 'plan') {
      wx.navigateTo({ url: `/pages/plan-detail/plan-detail?id=${id}` });
      return;
    }
    wx.navigateTo({ url: `/pages/community-detail/community-detail?id=${id}` });
  },

  normalizeTone(tone) {
    const value = `${tone || ''}`.toLowerCase();
    if (['gold', 'yellow', 'warm', 'citrine'].includes(value)) return 'gold';
    if (['violet', 'purple', 'amethyst'].includes(value)) return 'violet';
    if (['pink', 'rose', 'love'].includes(value)) return 'pink';
    if (['black', 'obsidian'].includes(value)) return 'black';
    if (['green', 'wood'].includes(value)) return 'green';
    if (['blue', 'aqua', 'aquamarine'].includes(value)) return 'blue';
    return 'clear';
  },

  toneForMaterial(item) {
    const element = `${item.element || ''}`;
    if (/木|wood/i.test(element)) return 'green';
    if (/火|fire/i.test(element)) return 'pink';
    if (/土|earth/i.test(element)) return 'gold';
    if (/金|metal/i.test(element)) return 'clear';
    if (/水|water/i.test(element)) return 'blue';
    return 'clear';
  }
});
