const auth = require('../../utils/auth');
const { getCommunityPosts } = require('../../utils/communityData');
const { getTodayDailyEnergy } = require('../../utils/api');

const TAB_BAR_PAGES = ['/pages/home/home', '/pages/community/community', '/pages/workspace/workspace', '/pages/profile/profile'];

Page({
  data: {
    daily: {
      vitality: 82,
      inspiration: 94,
      color: '海盐蓝',
      number: 7,
      stone: '海蓝宝',
      loginHint: '登录后获取你的今日能量'
    },
    bestSellers: [
      { name: '月光石轻眠', desc: '睡前放松', price: 268, tone: 'blue', recipe: ['moonstone', 'clearQuartz', 'aquamarine'] },
      { name: '黄水晶进阶', desc: '事业行动力', price: 328, tone: 'gold', recipe: ['citrine', 'tigerEye', 'clearQuartz'] },
      { name: '紫水晶灵感', desc: '创作专注', price: 298, tone: 'violet', recipe: ['amethyst', 'clearQuartz', 'moonstone'] }
    ],
    inspirations: getCommunityPosts().filter(item => ['ocean', 'clear', 'love', 'black'].includes(item.id)),
    inspirationCart: [],
    showStoneSheet: false,
    dailyStoneDetail: null
  },

  onShow() {
    // Daily energy is loaded on tap so a transient network issue does not block entry.
    this.setData({ inspirationCart: wx.getStorageSync('inspirationCart') || [] });
  },

  async loadDailyEnergy(userId) {
    try {
      const daily = await getTodayDailyEnergy(userId);
      this.setData({
        daily: {
          vitality: daily.score || this.data.daily.vitality,
          inspiration: daily.score || this.data.daily.inspiration,
          color: daily.lucky_color || this.data.daily.color,
          number: daily.lucky_number || this.data.daily.number,
          stone: daily.recommended_stone || this.data.daily.stone,
          loginHint: daily.title || daily.summary || '今日能量已更新'
        }
      });
    } catch (error) {
      console.warn('daily energy skipped:', error.message || error);
    }
  },

  async onDailyTap() {
    try {
      const user = await auth.requireLogin('登录后才能查看你的每日能量补给。');
      this.loadDailyEnergy(user.user_id);
    } catch (error) {
      // requireLogin already shows the guide.
    }
  },

  goToPage(e) {
    const url = e.currentTarget.dataset.url;
    if (!url) return;
    if (TAB_BAR_PAGES.includes(url)) {
      wx.switchTab({ url });
      return;
    }
    wx.navigateTo({ url });
  },

  openInspiration(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/community-detail/community-detail?id=${id}` });
  },

  onDailyStoneTap() {
    const stone = this.data.daily.stone || '海蓝宝';
    const detailMap = {
      海蓝宝: { name: '海蓝宝', tone: 'blue', desc: '适合沟通、平静和情绪整理。今天先把表达放慢一点。', recipe: ['aquamarine', 'clearQuartz', 'moonstone'] },
      紫水晶: { name: '紫水晶', tone: 'violet', desc: '适合灵感、专注和睡眠前的放松。', recipe: ['amethyst', 'clearQuartz', 'moonstone'] },
      黄水晶: { name: '黄水晶', tone: 'gold', desc: '适合行动力、目标感和财富议题。', recipe: ['citrine', 'tigerEye', 'clearQuartz'] }
    };
    this.setData({
      dailyStoneDetail: detailMap[stone] || { name: stone, tone: 'blue', desc: '适合今天的能量状态，可作为主石或点缀珠。', recipe: ['aquamarine', 'clearQuartz'] },
      showStoneSheet: true
    });
  },

  quickAddProduct(e) {
    const name = e.currentTarget.dataset.name;
    const product = this.data.bestSellers.find(item => item.name === name);
    if (!product) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const exists = cart.some(item => item.name === product.name);
    const nextCart = exists ? cart : [{ ...product, addedAt: Date.now() }, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    this.setData({ inspirationCart: nextCart });
    wx.showToast({ title: exists ? '灵感单里已有' : '已加入灵感单', icon: 'none' });
  },

  addDailyStoneToCart() {
    const detail = this.data.dailyStoneDetail;
    if (!detail) return;
    const cart = wx.getStorageSync('inspirationCart') || [];
    const item = {
      name: `${detail.name}今日能量`,
      desc: detail.desc,
      price: 0,
      tone: detail.tone,
      recipe: detail.recipe,
      addedAt: Date.now()
    };
    const exists = cart.some(entry => entry.name === item.name);
    const nextCart = exists ? cart : [item, ...cart];
    wx.setStorageSync('inspirationCart', nextCart);
    this.setData({ inspirationCart: nextCart, showStoneSheet: false });
    wx.showToast({ title: exists ? '灵感单里已有' : '已加入灵感单', icon: 'none' });
  },

  startDailyStoneDiy() {
    const detail = this.data.dailyStoneDetail;
    if (!detail) return;
    wx.setStorageSync('recommendedRecipe', detail.recipe);
    wx.setStorageSync('workspacePreset', 'recommended');
    this.setData({ showStoneSheet: false });
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  closeStoneSheet() {
    this.setData({ showStoneSheet: false });
  },

  noop() {},

  viewInspirationCart() {
    const cart = this.data.inspirationCart;
    if (!cart.length) {
      wx.showToast({ title: '灵感单还是空的', icon: 'none' });
      return;
    }
    wx.showModal({
      title: `灵感单 ${cart.length} 件`,
      content: cart.map(item => item.name).join('、'),
      confirmText: '去DIY',
      cancelText: '继续逛',
      success: res => {
        if (res.confirm) {
          const first = cart[0];
          wx.setStorageSync('recommendedRecipe', first.recipe || ['clearQuartz']);
          wx.setStorageSync('workspacePreset', 'recommended');
          wx.switchTab({ url: '/pages/workspace/workspace' });
        }
      }
    });
  },

  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' });
  }
});
